# -*- encoding: utf-8 -*-
"""
GTC Stock — Données d'exemple et accès aux données.

Les rapprochements et alertes ci-dessous restent des données factices
en mémoire (pas encore de base de données pour ces objets métier).
Les comptes utilisateurs, articles, entrées et sorties de stock sont
en revanche stockés dans une vraie base SQLite via SQLAlchemy (voir
apps/models.py et apps/config.py).
"""

from datetime import datetime

from flask import session
from sqlalchemy import false as sa_false
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from apps import db
from apps.models import (
    Utilisateur, Article, Entree, Sortie, Fournisseur, JournalActivite,
    Magasin, ROLES_TOUS_MAGASINS,
)
from apps import sage_connector
from apps import mailer


# ---------------------------------------------------------------------
# Filtrage par magasin (multi-magasin)
#
# Un "Gestionnaire de stock" est rattaché à un magasin (Utilisateur.
# magasin_id) et ne voit que les articles de ce magasin. Un
# "Administrateur" ou un "Comptable" (voir ROLES_TOUS_MAGASINS) voit
# tous les magasins, avec la possibilité d'en sélectionner un via le
# menu de la barre supérieure — ce choix est mémorisé dans
# session['magasin_filtre'].
# ---------------------------------------------------------------------


def _utilisateur_courant():
    """L'objet Utilisateur de la session courante, ou None hors session
    (ex. page de connexion)."""
    identifiant = session.get('identifiant')
    return get_user_by_identifiant(identifiant) if identifiant else None


def _scope_magasin():
    """Périmètre d'affichage courant, sous la forme (mode, magasin_id) :
      - ("tous", None)    : aucun filtre (admin/comptable sans sélection,
                            ou hors session) ;
      - ("magasin", <id>) : restreint à ce magasin (gestionnaire de
                            stock, ou admin/comptable ayant choisi un
                            magasin dans le menu) ;
      - ("aucun", None)   : rien de visible — gestionnaire de stock sans
                            magasin rattaché (à corriger par un admin).
    """
    user = _utilisateur_courant()
    if user is None:
        return ("tous", None)
    if user.role in ROLES_TOUS_MAGASINS:
        choisi = session.get('magasin_filtre')
        return ("magasin", int(choisi)) if choisi else ("tous", None)
    return ("magasin", user.magasin_id) if user.magasin_id else ("aucun", None)


def _filtrer_articles(query):
    """Restreint une requête sur Article au périmètre magasin courant."""
    mode, magasin_id = _scope_magasin()
    if mode == "magasin":
        return query.filter(Article.magasin_id == magasin_id)
    if mode == "aucun":
        return query.filter(sa_false())
    return query


def _article_visible(article):
    """True si `article` est dans le périmètre magasin courant."""
    mode, magasin_id = _scope_magasin()
    if mode == "tous":
        return True
    if mode == "magasin":
        return article.magasin_id == magasin_id
    return False


def get_all_magasins():
    """Tous les magasins, triés par nom (pour le menu de filtre et la
    page de gestion des magasins)."""
    return Magasin.query.order_by(Magasin.nom).all()


def get_magasins_detailles():
    """Magasins triés par nom, avec le nombre d'articles et de
    gestionnaires rattachés — pour la page de gestion des magasins."""
    lignes = []
    for magasin in get_all_magasins():
        lignes.append({
            "magasin": magasin,
            "nb_articles": Article.query.filter_by(magasin_id=magasin.id).count(),
            "nb_gestionnaires": Utilisateur.query.filter_by(magasin_id=magasin.id).count(),
        })
    return lignes


def _valider_email(valeur):
    """Normalise une adresse e-mail saisie : renvoie la chaîne nettoyée,
    None si vide, et lève ValueError si elle n'a manifestement pas la
    forme d'une adresse (contrôle volontairement minimal)."""
    valeur = (valeur or "").strip()
    if not valeur:
        return None
    if " " in valeur or valeur.count("@") != 1 or "." not in valeur.split("@")[1]:
        raise ValueError("L'adresse e-mail d'alerte n'est pas valide.")
    return valeur


def add_magasin(nom, adresse, email_alertes=None):
    """Crée un magasin en base. Lève ValueError si le nom est vide ou
    déjà pris (la contrainte d'unicité en base fait foi, comme pour
    add_fournisseur / add_user), ou si l'e-mail d'alerte est mal formé."""
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("Le nom du magasin est obligatoire.")
    email_alertes = _valider_email(email_alertes)
    if Magasin.query.filter_by(nom=nom).first():
        raise ValueError("Ce magasin existe déjà.")

    magasin = Magasin(nom=nom, adresse=(adresse or "").strip() or None,
                      email_alertes=email_alertes)
    db.session.add(magasin)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Ce magasin existe déjà.")
    return magasin


def maj_magasin_email(magasin_id, email_alertes):
    """Met à jour (ou efface, si vide) l'adresse d'alerte d'un magasin.
    Lève ValueError si le magasin est introuvable ou l'adresse mal
    formée."""
    magasin = db.session.get(Magasin, magasin_id)
    if magasin is None:
        raise ValueError("Magasin introuvable.")
    magasin.email_alertes = _valider_email(email_alertes)
    db.session.commit()
    return magasin


def maj_magasin(magasin_id, nom, adresse, email_alertes=None):
    """Modifie le nom, l'adresse et l'e-mail d'alerte d'un magasin
    existant. Mêmes règles de validation que add_magasin (nom
    obligatoire, unique, e-mail bien formé). Le nom peut changer même si
    des articles ou des utilisateurs sont rattachés au magasin : le
    rattachement se fait par id, pas par nom. Lève ValueError si le
    magasin est introuvable, si le nom est vide ou déjà porté par un
    autre magasin, ou si l'e-mail est mal formé."""
    magasin = db.session.get(Magasin, magasin_id)
    if magasin is None:
        raise ValueError("Magasin introuvable.")
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("Le nom du magasin est obligatoire.")
    email_alertes = _valider_email(email_alertes)
    if Magasin.query.filter(Magasin.nom == nom, Magasin.id != magasin_id).first():
        raise ValueError("Ce magasin existe déjà.")

    magasin.nom = nom
    magasin.adresse = (adresse or "").strip() or None
    magasin.email_alertes = email_alertes
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Ce magasin existe déjà.")
    return magasin


def _journaliser(utilisateur, action, description):
    """Ajoute une ligne au journal d'activité (audit log). N'effectue
    pas le commit elle-même : appelée juste avant le commit existant de
    l'action en cours, pour que le journal et l'action restent
    cohérents (même transaction)."""
    db.session.add(JournalActivite(
        horodatage=datetime.now(),
        utilisateur_id=utilisateur.id if utilisateur else None,
        identifiant=utilisateur.identifiant if utilisateur else None,
        action=action, description=description,
    ))


def get_journal():
    """Toutes les entrées du journal d'activité, de la plus récente à
    la plus ancienne."""
    return JournalActivite.query.order_by(
        JournalActivite.horodatage.desc(), JournalActivite.id.desc()
    ).all()

# ---------------------------------------------------------------------
# Articles, entrées et sorties de stock
#
# Stockés en base (tables "articles", "entrees", "sorties", voir
# apps/models.py). Les 5 articles et les 10 mouvements de démonstration
# sont insérés comme données initiales par la migration
# 0340cf32b856_creer_tables_articles_fournisseurs_*.py.
# ---------------------------------------------------------------------

# Seuil de stock en dessous (ou égal) duquel un article passe "Alerte" ;
# au-dessus, "OK" (sauf s'il reste "Dormant", statut non recalculé
# automatiquement — voir _recalculer_statut ci-dessous).
def _recalculer_statut(article):
    """Met à jour article.statut selon quantite vs seuil, après un
    mouvement. Un mouvement vient de se produire : l'article ne peut
    plus être considéré "Dormant" (aucune activité récente)."""
    article.statut = "Alerte" if article.quantite <= article.seuil else "OK"


# ---------------------------------------------------------------------
# Rapprochement automatique avec Sage 100
#
# Données de démonstration, utilisées tant que la connexion Sage 100 en
# base réelle (voir apps/sage_connector.py) n'est pas configurée — voir
# get_rapprochement() ci-dessous, appelée par la page /pages/rapprochement/.
# ---------------------------------------------------------------------
RAPPROCHEMENT = [
    {"article": "Rame de papier A4", "qte_app": 5, "qte_sage": 5, "ecart": 0, "conforme": True},
    {"article": "Classeur A4", "qte_app": 8, "qte_sage": 11, "ecart": -3, "conforme": False},
    {"article": "Cartouche imprimante", "qte_app": 50, "qte_sage": 50, "ecart": 0, "conforme": True},
    {"article": "Stylo bille bleu (boîte)", "qte_app": 96, "qte_sage": 90, "ecart": 6, "conforme": False},
    {"article": "Chaise bureau (modèle X)", "qte_app": 14, "qte_sage": 14, "ecart": 0, "conforme": True},
]

# ---------------------------------------------------------------------
# Alertes (écarts de rapprochement + seuils critiques)
# ---------------------------------------------------------------------
ALERTES = [
    {
        "titre": "Écart de rapprochement — Classeur A4",
        "detail": "Quantité application : 8 — Quantité Sage 100 : 11 (écart de -3)",
        "date": "24/08/2026 à 07:12",
        "type": "ecart",
        "icone": "bi-shield-exclamation",
        "traitee": False,
    },
    {
        "titre": "Écart de rapprochement — Stylo bille bleu (boîte)",
        "detail": "Quantité application : 96 — Quantité Sage 100 : 90 (écart de +6)",
        "date": "24/08/2026 à 07:12",
        "type": "ecart",
        "icone": "bi-shield-exclamation",
        "traitee": False,
    },
    {
        "titre": "Seuil critique atteint — Rame de papier A4",
        "detail": "Quantité actuelle : 5 — Seuil d'alerte : 10",
        "date": "22/08/2026 à 16:40",
        "type": "seuil",
        "icone": "bi-exclamation-triangle",
        "traitee": True,
    },
    {
        "titre": "Seuil critique atteint — Classeur A4",
        "detail": "Quantité actuelle : 8 — Seuil d'alerte : 15",
        "date": "21/08/2026 à 09:05",
        "type": "seuil",
        "icone": "bi-exclamation-triangle",
        "traitee": False,
    },
]

# ---------------------------------------------------------------------
# Comptes utilisateurs (vue administrateur)
#
# Stockés en base (table "utilisateurs", voir apps/models.py). Les
# quatre comptes de démonstration (j.dupont, m.kouam, p.meka administrateur,
# s.nkolo désactivé) sont insérés comme données initiales par la première
# migration (voir migrations/versions/276120d6d4b9_*.py) — leurs mots de
# passe par défaut n'y sont documentés qu'à titre de dev local et sont
# surchargeables via variables d'environnement (voir cette migration) :
# à changer avant tout déploiement réellement exposé.
# ---------------------------------------------------------------------


def get_stats():
    """Chiffres agrégés pour les cartes du tableau de bord (limités au
    magasin courant — voir _scope_magasin)."""
    articles = _filtrer_articles(Article.query).all()
    return {
        "total_articles": len(articles),
        "alertes": sum(1 for a in articles if a.statut_classe == "alerte"),
        "dormants": sum(1 for a in articles if a.statut_classe == "dormant"),
        "ecarts": sum(1 for a in articles if a.ecart),
    }


def get_all_articles():
    """Retourne les articles du magasin courant, triés par nom (voir
    _scope_magasin pour la règle de visibilité selon le rôle)."""
    return _filtrer_articles(Article.query).order_by(Article.nom).all()


def get_article(article_id):
    """Retourne l'article correspondant à l'id, ou None si absent,
    invalide, ou hors du périmètre magasin de l'utilisateur courant.
    Ce dernier cas sert aussi de garde-fou aux saisies d'entrée/sortie
    (add_entree/add_sortie passent par ici)."""
    if not article_id:
        return None
    article = db.session.get(Article, article_id)
    if article is None or not _article_visible(article):
        return None
    return article


def get_rapprochement():
    """Lignes de rapprochement stock application / Sage 100.

    Retourne (lignes, sage_connecte, erreur) :
      - si la connexion Sage 100 est configurée et fonctionne, compare en
        direct les quantités Sage aux quantités internes (sage_connecte=True) ;
      - sinon (non configurée, ou échec de connexion/requête), retourne
        les données de démonstration RAPPROCHEMENT (sage_connecte=False),
        avec le détail de l'erreur le cas échéant pour l'afficher à
        l'utilisateur plutôt que de masquer le problème."""
    if not sage_connector.is_configured():
        return _lignes_demo_visibles(RAPPROCHEMENT, lambda l: l["article"]), False, None

    try:
        quantites_sage = sage_connector.get_quantites_sage()
    except sage_connector.SageConnectorError as e:
        return _lignes_demo_visibles(RAPPROCHEMENT, lambda l: l["article"]), False, str(e)

    lignes = []
    for article in get_all_articles():
        qte_sage = quantites_sage.get(article.reference)
        if qte_sage is None:
            continue  # article absent de la base Sage : pas de comparaison possible
        ecart = article.quantite - qte_sage
        lignes.append({
            "article": article.nom,
            "qte_app": article.quantite,
            "qte_sage": qte_sage,
            "ecart": ecart,
            "conforme": ecart == 0,
        })
    return lignes, True, None


def _lignes_demo_visibles(lignes, nom_article):
    """Filtre une liste de dictionnaires de démonstration (RAPPROCHEMENT,
    ALERTES) sur le magasin courant, au mieux : une ligne est conservée
    si le nom d'article qu'elle mentionne (extrait par `nom_article`,
    qui peut renvoyer le nom exact ou un libellé qui le contient)
    correspond à un article visible. `lignes` est renvoyée telle quelle
    quand aucun filtre n'est actif (admin/comptable sans sélection)."""
    mode, _magasin_id = _scope_magasin()
    if mode == "tous":
        return lignes
    noms_visibles = {a.nom for a in get_all_articles()}
    return [
        ligne for ligne in lignes
        if any(nom in nom_article(ligne) for nom in noms_visibles)
    ]


def get_alertes():
    """Alertes de démonstration limitées au magasin courant (voir
    _lignes_demo_visibles). Les alertes en dur ne sont pas encore
    rattachées à un magasin en base : le rapprochement se fait sur le
    nom d'article cité dans le titre."""
    return _lignes_demo_visibles(ALERTES, lambda al: al["titre"])


def _mouvement_vers_dict(mouvement, type_libelle, signe):
    """Formate une ligne Entree/Sortie pour l'affichage (gabarit commun
    aux pages entrées/sorties et fiche de stock)."""
    return {
        "date": mouvement.date.strftime("%d/%m/%Y"),
        "date_tri": mouvement.date,
        "id_tri": mouvement.id,
        "article": mouvement.article.nom,
        "article_id": mouvement.article_id,
        "type": type_libelle,
        "reference": mouvement.reference or "—",
        "quantite": f"{signe}{mouvement.quantite}",
        "quantite_brute": mouvement.quantite,
        "saisi_par": mouvement.utilisateur.nom if mouvement.utilisateur else "—",
    }


def get_mouvements():
    """Mouvements (entrées + sorties) des articles du magasin courant,
    du plus récent au plus ancien — pour la page Entrées/Sorties."""
    entrees = _filtrer_articles(Entree.query.join(Article)).all()
    sorties = _filtrer_articles(Sortie.query.join(Article)).all()
    lignes = [_mouvement_vers_dict(e, "Entrée", "+") for e in entrees]
    lignes += [_mouvement_vers_dict(s, "Sortie", "-") for s in sorties]
    lignes.sort(key=lambda m: (m["date_tri"], m["id_tri"]), reverse=True)
    return lignes


def get_historique(article_id):
    """Historique des mouvements d'un article, du plus récent au plus
    ancien, avec le solde de stock après chaque mouvement (calculé à
    rebours depuis la quantité actuelle — pas besoin de le stocker)."""
    article = get_article(article_id)
    if not article:
        return []

    lignes = [_mouvement_vers_dict(e, "Entrée", "+") for e in Entree.query.filter_by(article_id=article_id)]
    lignes += [_mouvement_vers_dict(s, "Sortie", "-") for s in Sortie.query.filter_by(article_id=article_id)]
    lignes.sort(key=lambda m: (m["date_tri"], m["id_tri"]), reverse=True)

    solde = article.quantite
    for ligne in lignes:
        ligne["solde"] = solde
        solde -= ligne["quantite_brute"] if ligne["type"] == "Entrée" else -ligne["quantite_brute"]
    return lignes


def get_all_fournisseurs():
    """Retourne tous les fournisseurs, triés par nom."""
    return Fournisseur.query.order_by(Fournisseur.nom).all()


def add_fournisseur(nom, contact):
    """Crée un nouveau fournisseur en base. Lève ValueError si ce nom
    existe déjà (y compris en cas de double soumission quasi simultanée :
    la contrainte d'unicité en base fait foi, pas seulement la
    vérification préalable — même précaution que pour add_user)."""
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("Le nom du fournisseur est obligatoire.")
    if Fournisseur.query.filter_by(nom=nom).first():
        raise ValueError("Ce fournisseur existe déjà.")

    fournisseur = Fournisseur(nom=nom, contact=(contact or "").strip() or None)
    db.session.add(fournisseur)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Ce fournisseur existe déjà.")
    return fournisseur


def add_article(nom, reference, seuil, quantite, fournisseur_id=None, magasin_id=None):
    """Crée un article au catalogue. Lève ValueError si un champ
    obligatoire manque ou est invalide, si la référence existe déjà (la
    contrainte d'unicité en base fait foi, pas seulement la vérification
    préalable — même précaution que pour add_user / add_fournisseur), ou
    si le fournisseur / le magasin indiqué est introuvable.

    Le statut initial est déduit de la quantité vs le seuil (même règle
    que _recalculer_statut) ; l'article démarre sans dernier mouvement."""
    nom = (nom or "").strip()
    reference = (reference or "").strip()
    if not nom:
        raise ValueError("La désignation de l'article est obligatoire.")
    if not reference:
        raise ValueError("La référence de l'article est obligatoire.")
    if len(nom) > 150:
        raise ValueError("La désignation est trop longue (150 caractères maximum).")
    if len(reference) > 50:
        raise ValueError("La référence est trop longue (50 caractères maximum).")
    if seuil is None or seuil < 0:
        raise ValueError("Le seuil d'alerte doit être un entier positif ou nul.")
    if quantite is None or quantite < 0:
        raise ValueError("La quantité initiale doit être un entier positif ou nul.")
    if not magasin_id or db.session.get(Magasin, magasin_id) is None:
        raise ValueError("Merci d'indiquer le magasin de rattachement de l'article.")

    fournisseur = None
    if fournisseur_id:
        fournisseur = db.session.get(Fournisseur, fournisseur_id)
        if fournisseur is None:
            raise ValueError("Fournisseur introuvable.")

    if Article.query.filter_by(reference=reference).first():
        raise ValueError(f"La référence « {reference} » existe déjà.")

    article = Article(
        nom=nom, reference=reference, seuil=seuil, quantite=quantite,
        fournisseur_id=fournisseur.id if fournisseur else None,
        magasin_id=magasin_id,
        statut="Alerte" if quantite <= seuil else "OK",
        dernier_mouvement="—",
    )
    db.session.add(article)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError(f"La référence « {reference} » existe déjà.")
    return article


def add_entree(article_id, date_mouvement, quantite, fournisseur_id, reference, utilisateur):
    """Enregistre une entrée de stock et met à jour l'article. Lève
    ValueError si l'article ou le fournisseur est introuvable, ou si la
    quantité est invalide."""
    article = get_article(article_id)
    if not article:
        raise ValueError("Article introuvable.")
    if quantite <= 0:
        raise ValueError("La quantité doit être supérieure à zéro.")
    fournisseur = db.session.get(Fournisseur, fournisseur_id) if fournisseur_id else None
    if not fournisseur:
        raise ValueError("Merci de sélectionner un fournisseur.")

    entree = Entree(
        article_id=article.id, date=date_mouvement, quantite=quantite,
        fournisseur_id=fournisseur.id, reference=reference or None,
        utilisateur_id=utilisateur.id if utilisateur else None,
    )
    article.quantite += quantite
    article.dernier_mouvement = date_mouvement.strftime("%d/%m/%Y")
    _recalculer_statut(article)

    db.session.add(entree)
    _journaliser(utilisateur, "entree_stock",
                 f"Entrée de {quantite} sur « {article.nom} » ({article.reference}).")
    db.session.commit()
    return entree


def add_sortie(article_id, date_mouvement, quantite, type_document, reference, utilisateur):
    """Enregistre une sortie de stock et met à jour l'article. Lève
    ValueError si l'article est introuvable, la quantité invalide, ou
    si le stock disponible est insuffisant (le stock ne peut jamais
    devenir négatif)."""
    article = get_article(article_id)
    if not article:
        raise ValueError("Article introuvable.")
    if quantite <= 0:
        raise ValueError("La quantité doit être supérieure à zéro.")
    if quantite > article.quantite:
        raise ValueError(
            f"Stock insuffisant : {article.quantite} disponible(s) pour "
            f"« {article.nom} », {quantite} demandé(s)."
        )

    sortie = Sortie(
        article_id=article.id, date=date_mouvement, quantite=quantite,
        type_document=type_document or None, reference=reference or None,
        utilisateur_id=utilisateur.id if utilisateur else None,
    )
    statut_avant = article.statut
    article.quantite -= quantite
    article.dernier_mouvement = date_mouvement.strftime("%d/%m/%Y")
    _recalculer_statut(article)
    # L'article vient-il de basculer en alerte avec cette sortie ? On
    # notifie uniquement sur la transition (pas à chaque sortie tant
    # qu'il reste en alerte) : le prochain e-mail n'aura lieu qu'après
    # être repassé au-dessus du seuil puis redescendu.
    bascule_en_alerte = statut_avant != "Alerte" and article.statut == "Alerte"

    db.session.add(sortie)
    _journaliser(utilisateur, "sortie_stock",
                 f"Sortie de {quantite} sur « {article.nom} » ({article.reference}).")
    db.session.commit()

    if bascule_en_alerte:
        # Après le commit : un échec d'envoi ne doit pas annuler la
        # sortie (mailer.envoyer_alerte_seuil n'élève jamais d'exception).
        mailer.envoyer_alerte_seuil(article)
    return sortie


def get_all_users():
    """Retourne tous les utilisateurs, triés par nom (vue administrateur)."""
    return Utilisateur.query.order_by(Utilisateur.nom).all()


def get_user_by_identifiant(identifiant):
    """Retourne l'utilisateur correspondant à l'identifiant, ou None."""
    return Utilisateur.query.filter_by(identifiant=identifiant).first()


# Hash factice utilisé quand l'identifiant est inconnu, pour que
# check_password_hash() soit systématiquement exécuté (même coût CPU)
# côté serveur — évite qu'un attaquant déduise par le temps de réponse
# si un identifiant existe (énumération de comptes).
_HASH_FACTICE = generate_password_hash("mot-de-passe-factice-temps-constant")


def verify_credentials(identifiant, mot_de_passe):
    """Vérifie identifiant/mot de passe. Retourne l'utilisateur si valide
    et actif, sinon None (compte inconnu, désactivé ou mot de passe faux).
    Met à jour la date de dernière connexion en cas de succès."""
    user = get_user_by_identifiant(identifiant)
    hash_a_verifier = user.mot_de_passe_hash if user else _HASH_FACTICE
    mot_de_passe_valide = check_password_hash(hash_a_verifier, mot_de_passe)

    if not user or not user.actif or not mot_de_passe_valide:
        return None

    user.derniere_connexion = datetime.now().strftime("%d/%m/%Y — %H:%M")
    _journaliser(user, "connexion", f"Connexion réussie de « {user.identifiant} ».")
    db.session.commit()
    return user


def add_user(nom, identifiant, role, mot_de_passe, magasin_id=None, cree_par=None):
    """Crée un nouvel utilisateur en base. Lève ValueError si
    l'identifiant existe déjà (y compris en cas de double soumission
    quasi simultanée : la contrainte d'unicité en base fait foi, pas
    seulement la vérification préalable). `magasin_id` n'a de sens que
    pour un « Gestionnaire de stock » (voir ROLES_TOUS_MAGASINS) ; il
    est ignoré (laissé à NULL) pour les autres rôles. `cree_par` est
    l'administrateur qui effectue la création (pour le journal
    d'activité — voir apps/models.py, JournalActivite), pas le nouveau
    compte lui-même."""
    if get_user_by_identifiant(identifiant):
        raise ValueError("Cet identifiant existe déjà.")
    if role in ROLES_TOUS_MAGASINS:
        magasin_id = None
    user = Utilisateur(nom=nom, identifiant=identifiant, role=role, actif=True,
                       magasin_id=magasin_id)
    user.set_password(mot_de_passe)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Cet identifiant existe déjà.")

    _journaliser(cree_par, "creation_utilisateur", f"Création du compte « {identifiant} » ({role}).")
    db.session.commit()
    return user
