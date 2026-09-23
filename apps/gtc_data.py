# -*- encoding: utf-8 -*-
"""
GTC Stock — Données d'exemple et accès aux données.

Le rapprochement ci-dessous reste une donnée factice en mémoire (pas
encore de base de données pour cet objet métier). Les comptes
utilisateurs, articles, entrées/sorties de stock et alertes sont en
revanche stockés dans une vraie base SQLite via SQLAlchemy (voir
apps/models.py et apps/config.py).
"""

from datetime import datetime

from flask import session
from sqlalchemy import false as sa_false, or_ as sa_or
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from apps import db
from apps.models import (
    Utilisateur, Article, Entree, Sortie, Transfert, Fournisseur, JournalActivite,
    Magasin, Alerte, ROLE_CLASSES, ROLES_TOUS_MAGASINS, TYPES_ENTREE, TYPES_SORTIE,
    ROLES_REGULARISATION,
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


def _filtrer_articles(query, inclure_archives=False):
    """Restreint une requête sur Article au périmètre magasin courant.
    Exclut aussi les articles archivés (suppression douce) sauf si
    `inclure_archives` — seul le rapprochement comptable les conserve,
    pour ne pas masquer silencieusement un écart avec Sage 100."""
    if not inclure_archives:
        query = query.filter(Article.archive.is_(False))
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


def _filtrer_alertes(query):
    """Restreint une requête sur Alerte au périmètre magasin courant
    (même logique que _filtrer_articles)."""
    mode, magasin_id = _scope_magasin()
    if mode == "magasin":
        return query.filter(Alerte.magasin_id == magasin_id)
    if mode == "aucun":
        return query.filter(sa_false())
    return query


def _alerte_visible(alerte):
    """True si `alerte` est dans le périmètre magasin courant."""
    mode, magasin_id = _scope_magasin()
    if mode == "tous":
        return True
    if mode == "magasin":
        return alerte.magasin_id == magasin_id
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


def vider_journal(acteur):
    """Vide le journal d'activité — à n'appeler qu'une fois l'export
    complet déjà généré avec succès (voir views._exporter_et_vider_journal,
    qui garantit cet ordre et n'appelle jamais cette fonction si la
    génération de l'export a échoué : on ne veut jamais perdre des lignes
    du journal sans archive correspondante).
    Supprime toutes les entrées existantes puis ajoute une unique entrée
    de traçabilité (qui a purgé, quand, combien de lignes) : il n'y a donc
    jamais de trou total dans l'audit log, même juste après une purge."""
    nb = JournalActivite.query.delete()
    _journaliser(
        acteur, "purge_journal",
        f"Journal d'activité vidé après export complet — {nb} entrée(s) archivée(s) puis supprimée(s).",
    )
    db.session.commit()
    return nb

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
# Alertes (écarts de rapprochement + seuils critiques) : voir la classe
# Alerte (apps/models.py) — stockées en base, alimentées par la
# migration alertes (données de démonstration initiales).
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


def get_all_articles(inclure_archives=False):
    """Retourne les articles du magasin courant, triés par nom (voir
    _scope_magasin pour la règle de visibilité selon le rôle). Les
    articles archivés sont exclus sauf si `inclure_archives`."""
    return _filtrer_articles(
        Article.query, inclure_archives=inclure_archives
    ).order_by(Article.nom).all()


def get_articles_archives():
    """Les seuls articles archivés du périmètre courant, triés par nom —
    pour la vue « Afficher les articles archivés » de la page Articles
    (réservée à l'administrateur)."""
    return _filtrer_articles(
        Article.query.filter(Article.archive.is_(True)), inclure_archives=True
    ).order_by(Article.nom).all()


def rechercher_articles(terme, magasin_id=None):
    """Articles actifs (non archivés) dont la référence OU la désignation
    contient `terme` (insensible à la casse), limité à 10 résultats — pour
    l'autocomplétion (type-ahead) des formulaires de mouvement (entrée,
    sortie, transfert) : jamais le catalogue entier chargé d'un coup, voir
    la route pages_articles_recherche.

    Périmètre :
      - si `magasin_id` est fourni ET que l'utilisateur courant a le droit
        de le consulter (rôle qui voit tous les magasins, ou c'est bien
        SON magasin de rattachement), restreint à ce seul magasin — c'est
        le cas du formulaire de transfert, où le magasin source choisi
        peut différer du filtre de la barre supérieure (session
        magasin_filtre) ; sinon (magasin_id absent, ou refusé) retombe
        sur le périmètre magasin courant habituel (_filtrer_articles),
        le même que get_all_articles() pour les formulaires Entrée/Sortie."""
    terme = (terme or "").strip()
    if not terme:
        return []

    query = Article.query.filter(Article.archive.is_(False))
    if magasin_id is not None:
        utilisateur = _utilisateur_courant()
        autorise = utilisateur is not None and (
            utilisateur.role in ROLES_TOUS_MAGASINS or utilisateur.magasin_id == magasin_id
        )
        if not autorise:
            return []
        query = query.filter(Article.magasin_id == magasin_id)
    else:
        query = _filtrer_articles(query)

    motif = f"%{terme}%"
    query = query.filter(sa_or(Article.reference.ilike(motif), Article.nom.ilike(motif)))
    articles = query.order_by(Article.nom).limit(10).all()
    # fournisseur_id/fournisseur_nom : transmis pour que le formulaire de
    # réception fournisseur (entrees.html) affiche/valide en une seule
    # requête le fournisseur rattaché à l'article choisi, sans aller-retour
    # réseau supplémentaire (voir static/assets/js/gtc-stock.js, section 5,
    # et le blocage correspondant côté serveur dans add_entree).
    return [
        {
            "id": a.id, "nom": a.nom, "reference": a.reference, "quantite": a.quantite,
            "fournisseur_id": a.fournisseur_id,
            "fournisseur_nom": a.fournisseur.nom if a.fournisseur else None,
        }
        for a in articles
    ]


def get_article(article_id, inclure_archives=False):
    """Retourne l'article correspondant à l'id, ou None si absent,
    invalide, hors du périmètre magasin de l'utilisateur courant, ou
    archivé (sauf si `inclure_archives`). Sert aussi de garde-fou aux
    saisies d'entrée/sortie (add_entree/add_sortie passent par ici : un
    article archivé n'accepte plus aucun mouvement)."""
    if not article_id:
        return None
    article = db.session.get(Article, article_id)
    if article is None or not _article_visible(article):
        return None
    if article.archive and not inclure_archives:
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
    # inclure_archives=True partout ici : un article archivé qui présente
    # encore un écart avec Sage 100 doit rester visible au rapprochement,
    # pas être masqué silencieusement.
    if not sage_connector.is_configured():
        return _lignes_demo_visibles(RAPPROCHEMENT, lambda l: l["article"],
                                     inclure_archives=True), False, None

    try:
        quantites_sage = sage_connector.get_quantites_sage()
    except sage_connector.SageConnectorError as e:
        return _lignes_demo_visibles(RAPPROCHEMENT, lambda l: l["article"],
                                     inclure_archives=True), False, str(e)

    lignes = []
    for article in get_all_articles(inclure_archives=True):
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


def _lignes_demo_visibles(lignes, nom_article, inclure_archives=False):
    """Filtre une liste de dictionnaires de démonstration (RAPPROCHEMENT)
    sur le magasin courant, au mieux : une ligne est conservée
    si le nom d'article qu'elle mentionne (extrait par `nom_article`,
    qui peut renvoyer le nom exact ou un libellé qui le contient)
    correspond à un article visible. `lignes` est renvoyée telle quelle
    quand aucun filtre n'est actif (admin/comptable sans sélection).
    `inclure_archives` est propagé à get_all_articles (le rapprochement
    conserve les articles archivés, pas la page Alertes)."""
    mode, _magasin_id = _scope_magasin()
    if mode == "tous":
        return lignes
    noms_visibles = {a.nom for a in get_all_articles(inclure_archives=inclure_archives)}
    return [
        ligne for ligne in lignes
        if any(nom in nom_article(ligne) for nom in noms_visibles)
    ]


def get_alertes():
    """Alertes du magasin courant (voir _filtrer_alertes), non traitées
    d'abord, les plus récentes en tête de chaque groupe."""
    return _filtrer_alertes(Alerte.query).order_by(
        Alerte.traitee.asc(), Alerte.id.desc()
    ).all()


def traiter_alerte(alerte_id, acteur=None):
    """Marque une alerte comme traitée (bouton « Marquer comme traitée »
    de la page Alertes). Lève ValueError si l'alerte est introuvable,
    hors périmètre, ou déjà traitée."""
    alerte = db.session.get(Alerte, alerte_id)
    if alerte is None or not _alerte_visible(alerte):
        raise ValueError("Alerte introuvable.")
    if alerte.traitee:
        raise ValueError("Cette alerte est déjà traitée.")
    alerte.traitee = True
    _journaliser(acteur, "traiter_alerte", f"Alerte traitée : « {alerte.titre} ».")
    db.session.commit()
    return alerte


def _mouvement_vers_dict(mouvement, type_libelle, signe):
    """Formate une ligne Entree/Sortie pour l'affichage (gabarit commun
    aux pages entrées/sorties et fiche de stock).

    `sous_type`/`sous_type_classe` (libellé + classe Bootstrap du badge —
    voir TYPES_ENTREE / TYPES_SORTIE) sont communs aux deux : une entrée
    et une sortie ont chacune leur propre sous-classification, affichée
    de la même façon. `detail` complète `reference` quand elle est vide
    (une régularisation n'a ni bordereau ni n° de document) : on retombe
    alors sur le motif, pour ne jamais afficher une ligne vide de tout
    contexte."""
    ligne = {
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
    # type_entree/type_sortie n'existent que sur Entree, respectivement
    # Sortie (voir apps/models.py) — jamais les deux sur le même objet,
    # d'où le getattr plutôt qu'un accès direct.
    type_entree = getattr(mouvement, "type_entree", None)
    type_sortie = getattr(mouvement, "type_sortie", None)
    if type_entree == "reception_fournisseur":
        ligne["sous_type"] = mouvement.type_entree_libelle
        ligne["sous_type_classe"] = mouvement.type_entree_classe
        ligne["detail"] = mouvement.num_bon_livraison_fournisseur or "—"
        # Affichés en plus du détail sur la fiche de stock seulement (voir
        # templates/pages/fiche_stock.html) — None ailleurs n'est jamais lu.
        ligne["numero_vehicule"] = mouvement.numero_vehicule
        ligne["nom_chauffeur"] = mouvement.nom_chauffeur
        ligne["num_bordereau_reception"] = mouvement.num_bordereau_reception
        # Fournisseur de CE mouvement (copié sur Entree.fournisseur_id au
        # moment de la réception — voir add_entree) : reste correct même si
        # le fournisseur habituel de l'article change ensuite. "—" au lieu
        # de None pour les quelques réceptions historiques enregistrées
        # avant l'ajout de ce champ (fournisseur_id resté NULL).
        ligne["fournisseur"] = mouvement.fournisseur.nom if mouvement.fournisseur else "—"
    elif type_entree:
        ligne["sous_type"] = mouvement.type_entree_libelle
        ligne["sous_type_classe"] = mouvement.type_entree_classe
        ligne["detail"] = mouvement.reference or mouvement.motif or "—"
    elif type_sortie:
        ligne["sous_type"] = mouvement.type_sortie_libelle
        ligne["sous_type_classe"] = mouvement.type_sortie_classe
        ligne["detail"] = mouvement.reference or mouvement.motif or "—"
    else:
        ligne["detail"] = ligne["reference"]
    return ligne


def get_entrees():
    """Entrées de stock des articles du magasin courant, de la plus
    récente à la plus ancienne — pour la page Entrées de stock."""
    entrees = _filtrer_articles(Entree.query.join(Article)).all()
    lignes = [_mouvement_vers_dict(e, "Entrée", "+") for e in entrees]
    lignes.sort(key=lambda m: (m["date_tri"], m["id_tri"]), reverse=True)
    return lignes


def get_sorties():
    """Sorties de stock des articles du magasin courant, de la plus
    récente à la plus ancienne — pour la page Sorties de stock."""
    sorties = _filtrer_articles(Sortie.query.join(Article)).all()
    lignes = [_mouvement_vers_dict(s, "Sortie", "-") for s in sorties]
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


def rechercher_fournisseurs(terme):
    """Fournisseurs dont le nom OU le contact contient `terme` (insensible
    à la casse), limité à 10 résultats — pour l'autocomplétion (type-ahead)
    du champ Fournisseur d'un article (voir la route
    pages_fournisseurs_recherche), même principe que rechercher_articles.
    Pas de filtrage par magasin : un fournisseur n'est pas rattaché à un
    magasin en particulier."""
    terme = (terme or "").strip()
    if not terme:
        return []

    motif = f"%{terme}%"
    fournisseurs = (
        Fournisseur.query
        .filter(sa_or(Fournisseur.nom.ilike(motif), Fournisseur.contact.ilike(motif)))
        .order_by(Fournisseur.nom)
        .limit(10)
        .all()
    )
    return [{"id": f.id, "nom": f.nom, "contact": f.contact} for f in fournisseurs]


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
    obligatoire manque ou est invalide, si la référence existe déjà DANS CE
    MAGASIN (la contrainte d'unicité en base fait foi, pas seulement la
    vérification préalable — même précaution que pour add_user /
    add_fournisseur ; la même référence reste, elle, tout à fait valide
    dans un autre magasin — voir Article.__table_args__), ou si le
    fournisseur / le magasin indiqué est introuvable.

    Le fournisseur est désormais OBLIGATOIRE (voir Article.fournisseur_id) :
    une réception fournisseur (add_entree) le dérive automatiquement de
    l'article plutôt que de le faire ressaisir à chaque mouvement — il n'y
    a donc plus de moment où « pas de fournisseur » serait rattrapable
    ailleurs. Les articles créés avant ce changement peuvent rester sans
    fournisseur (colonne restée nullable en base, pour ne pas casser les
    données existantes) ; add_entree bloque alors leur réception tant que
    la fiche n'a pas été complétée (voir son message d'erreur dédié).

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

    if not fournisseur_id:
        raise ValueError("Merci de sélectionner le fournisseur habituel de l'article.")
    fournisseur = db.session.get(Fournisseur, fournisseur_id)
    if fournisseur is None:
        raise ValueError("Fournisseur introuvable.")

    if Article.query.filter_by(reference=reference, magasin_id=magasin_id).first():
        raise ValueError(f"La référence « {reference} » existe déjà dans ce magasin.")

    article = Article(
        nom=nom, reference=reference, seuil=seuil, quantite=quantite,
        fournisseur_id=fournisseur.id,
        magasin_id=magasin_id,
        statut="Alerte" if quantite <= seuil else "OK",
        dernier_mouvement="—",
    )
    db.session.add(article)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError(f"La référence « {reference} » existe déjà dans ce magasin.")
    return article


def maj_article(article_id, nom, seuil, fournisseur_id=None,
                magasin_id=None, peut_changer_magasin=False):
    """Modifie le catalogue d'un article : désignation, seuil d'alerte,
    fournisseur habituel, et — seulement si `peut_changer_magasin` (rôle
    Administrateur) — le magasin de rattachement.

    La référence et la quantité en stock ne sont JAMAIS touchées ici :
    la référence est l'identifiant fixe de l'article, et la quantité ne
    change que par de vrais mouvements d'entrée/sortie (même règle que
    l'import de fichier). Le statut Alerte/OK est réaligné sur le nouveau
    seuil, sauf pour un article « Dormant » qu'on laisse tel quel (idem
    import).

    L'article est résolu via get_article() : un Gestionnaire de stock ne
    peut pas modifier un article hors de son magasin (ValueError « Article
    introuvable »). Lève aussi ValueError si la désignation est vide/trop
    longue, si le seuil est négatif, si le fournisseur est absent ou
    introuvable (désormais obligatoire — voir add_article), si le magasin
    indiqué est introuvable, ou si sa référence existe déjà dans le
    magasin de destination choisi (la référence n'étant unique QUE par
    magasin — voir Article.__table_args__ — déplacer un article peut
    désormais entrer en conflit avec un article homonyme déjà présent
    là-bas)."""
    article = get_article(article_id)
    if article is None:
        raise ValueError("Article introuvable.")
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("La désignation de l'article est obligatoire.")
    if len(nom) > 150:
        raise ValueError("La désignation est trop longue (150 caractères maximum).")
    if seuil is None or seuil < 0:
        raise ValueError("Le seuil d'alerte doit être un entier positif ou nul.")

    if not fournisseur_id:
        raise ValueError("Merci de sélectionner le fournisseur habituel de l'article.")
    if db.session.get(Fournisseur, fournisseur_id) is None:
        raise ValueError("Fournisseur introuvable.")

    if peut_changer_magasin:
        if not magasin_id or db.session.get(Magasin, magasin_id) is None:
            raise ValueError("Merci d'indiquer le magasin de rattachement de l'article.")
        if magasin_id != article.magasin_id and Article.query.filter_by(
            reference=article.reference, magasin_id=magasin_id
        ).first():
            raise ValueError(
                f"La référence « {article.reference} » existe déjà dans le magasin de destination."
            )
        article.magasin_id = magasin_id

    article.nom = nom
    article.seuil = seuil
    article.fournisseur_id = fournisseur_id
    if article.statut != "Dormant":
        article.statut = "Alerte" if article.quantite <= seuil else "OK"
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError(
            f"La référence « {article.reference} » existe déjà dans le magasin de destination."
        )
    return article


def archiver_article(article_id, acteur=None):
    """Archive un article (suppression douce) : il sort des vues
    opérationnelles et n'accepte plus aucun mouvement, mais reste en base
    avec tout son historique. L'accès est contrôlé par la route
    (Gestionnaire de stock ou Administrateur). Lève ValueError si
    l'article est introuvable ou hors périmètre, ou s'il est déjà
    archivé."""
    article = db.session.get(Article, article_id)
    if article is None or not _article_visible(article):
        raise ValueError("Article introuvable.")
    if article.archive:
        raise ValueError("Cet article est déjà archivé.")
    article.archive = True
    _journaliser(acteur, "archive_article",
                 f"Archivage de l'article « {article.nom} » ({article.reference}).")
    db.session.commit()
    return article


def desarchiver_article(article_id, acteur=None):
    """Réactive un article archivé : il réapparaît dans les vues et
    accepte de nouveau des mouvements. Réservé à l'administrateur
    (contrôlé par la route). Lève ValueError si l'article est introuvable
    ou hors périmètre, ou s'il n'est pas archivé."""
    article = db.session.get(Article, article_id)
    if article is None or not _article_visible(article):
        raise ValueError("Article introuvable.")
    if not article.archive:
        raise ValueError("Cet article n'est pas archivé.")
    article.archive = False
    _journaliser(acteur, "desarchive_article",
                 f"Désarchivage de l'article « {article.nom} » ({article.reference}).")
    db.session.commit()
    return article


def supprimer_definitivement_article(article_id, acteur=None):
    """Supprime DÉFINITIVEMENT un article déjà archivé, avec tout son
    historique de mouvements (entrées, sorties) — action irréversible,
    réservée à l'administrateur (contrôlé par la route). À la différence
    d'archiver_article (suppression douce, réversible), la ligne
    disparaît vraiment de la base : à réserver aux cas où l'historique
    n'a plus besoin d'être conservé (le rapprochement Sage 100 n'étant
    pas encore une table dédiée — voir get_rapprochement — il n'y a pas
    d'autre donnée liée à purger explicitement). Lève ValueError si
    l'article est introuvable, hors périmètre, ou pas archivé (on ne
    supprime définitivement qu'un article déjà mis de côté, jamais un
    article encore actif)."""
    article = db.session.get(Article, article_id)
    if article is None or not _article_visible(article):
        raise ValueError("Article introuvable.")
    if not article.archive:
        raise ValueError("Seul un article archivé peut être supprimé définitivement.")

    nom, reference = article.nom, article.reference
    nb_entrees = Entree.query.filter_by(article_id=article.id).delete()
    nb_sorties = Sortie.query.filter_by(article_id=article.id).delete()
    db.session.delete(article)
    _journaliser(acteur, "suppression_article",
                 f"Suppression définitive de l'article « {nom} » ({reference}) "
                 f"— {nb_entrees} entrée(s) et {nb_sorties} sortie(s) supprimées avec lui.")
    db.session.commit()
    return {"nom": nom, "reference": reference, "nb_entrees": nb_entrees, "nb_sorties": nb_sorties}


def _article_mouvementable(article_id):
    """Article visible ET non archivé, pour add_entree / add_sortie.
    Lève ValueError avec un message distinct selon le cas : introuvable /
    hors périmètre, ou archivé (aucun mouvement possible tant qu'il n'est
    pas désarchivé)."""
    article = get_article(article_id, inclure_archives=True)
    if article is None:
        raise ValueError("Article introuvable.")
    if article.archive:
        raise ValueError(
            f"L'article « {article.nom} » est archivé : aucun mouvement ne peut y être "
            "enregistré. Désarchivez-le d'abord."
        )
    return article


def add_entree(article_id, date_mouvement, quantite, type_entree, utilisateur, *,
                magasin_id=None, reference=None, motif=None,
                numero_vehicule=None, nom_chauffeur=None, num_bon_livraison_fournisseur=None,
                num_bordereau_reception=None):
    """Enregistre une entrée de stock et met à jour l'article. `type_entree`
    (voir TYPES_ENTREE) détermine quels champs — tous passés en mots-clés,
    seuls certains sont exigés selon le type — sont réellement utilisés :
      - "reception_fournisseur" : magasin_id (le magasin concerné par la
        réception — doit être celui de l'article), numero_vehicule,
        nom_chauffeur, num_bon_livraison_fournisseur ET
        num_bordereau_reception — tous obligatoires : une vraie réception
        physique a un véhicule, un chauffeur, et DEUX documents distincts
        (le bon de livraison, émis par le fournisseur, et le bordereau de
        réception, établi en interne — jamais l'un pour l'autre). Le
        fournisseur N'EST PLUS un paramètre : il est repris automatiquement
        d'Article.fournisseur_id (aucun choix/saisie à ce niveau) — voir
        ValueError dédiée ci-dessous si l'article n'en a pas ;
      - "retour_client" : reference (nom/référence du client) ; motif
        (motif du retour) reste facultatif ;
      - "regularisation" : motif obligatoire, réservée aux rôles
        ROLES_REGULARISATION (Administrateur / Gestionnaire de stock) —
        pas de fournisseur ni de référence externe (aucun document réel).

    Lève ValueError si l'article est introuvable, si `type_entree` est
    invalide, si un champ obligatoire pour ce type manque, si l'article
    n'appartient pas au magasin indiqué (réception), si l'article n'a pas
    de fournisseur rattaché (réception — message invitant à compléter sa
    fiche d'abord), si le rôle de `utilisateur` n'autorise pas une
    régularisation, ou si la quantité est invalide."""
    article = _article_mouvementable(article_id)
    if quantite <= 0:
        raise ValueError("La quantité doit être supérieure à zéro.")
    if type_entree not in TYPES_ENTREE:
        raise ValueError("Type d'entrée invalide.")

    reference = (reference or "").strip() or None
    motif = (motif or "").strip() or None
    numero_vehicule = (numero_vehicule or "").strip() or None
    nom_chauffeur = (nom_chauffeur or "").strip() or None
    num_bon_livraison_fournisseur = (num_bon_livraison_fournisseur or "").strip() or None
    num_bordereau_reception = (num_bordereau_reception or "").strip() or None
    fournisseur_id = None

    if type_entree == "reception_fournisseur":
        if not magasin_id:
            raise ValueError("Merci d'indiquer le magasin concerné par la réception.")
        if article.magasin_id != magasin_id:
            raise ValueError("L'article sélectionné n'appartient pas au magasin concerné par la réception.")
        if not article.fournisseur_id:
            raise ValueError(
                f"« {article.nom} » n'a pas de fournisseur rattaché : complétez d'abord sa fiche "
                "(page Articles) avant d'enregistrer une réception."
            )
        fournisseur_id = article.fournisseur_id
        if not numero_vehicule:
            raise ValueError("Merci d'indiquer le numéro du véhicule de livraison.")
        if not nom_chauffeur:
            raise ValueError("Merci d'indiquer le nom du chauffeur.")
        if not num_bon_livraison_fournisseur:
            raise ValueError("Merci d'indiquer le numéro du bon de livraison fournisseur.")
        if not num_bordereau_reception:
            raise ValueError("Merci d'indiquer le numéro du bordereau de réception.")
        reference = None  # ces deux numéros vivent désormais dans leurs propres colonnes
    elif type_entree == "retour_client":
        if not reference:
            raise ValueError("Merci d'indiquer le nom ou la référence du client.")
        numero_vehicule = nom_chauffeur = num_bon_livraison_fournisseur = None
        num_bordereau_reception = None
    elif type_entree == "regularisation":
        if utilisateur is None or utilisateur.role not in ROLES_REGULARISATION:
            raise ValueError(
                "Seuls un Administrateur ou un Gestionnaire de stock peuvent "
                "enregistrer une régularisation."
            )
        if not motif:
            raise ValueError("Merci d'indiquer le motif de la régularisation.")
        reference = None  # pas de document externe pour une régularisation
        numero_vehicule = nom_chauffeur = num_bon_livraison_fournisseur = None
        num_bordereau_reception = None

    entree = Entree(
        article_id=article.id, date=date_mouvement, quantite=quantite,
        type_entree=type_entree,
        fournisseur_id=fournisseur_id,
        reference=reference, motif=motif,
        numero_vehicule=numero_vehicule, nom_chauffeur=nom_chauffeur,
        num_bon_livraison_fournisseur=num_bon_livraison_fournisseur,
        num_bordereau_reception=num_bordereau_reception,
        utilisateur_id=utilisateur.id if utilisateur else None,
    )
    article.quantite += quantite
    article.dernier_mouvement = date_mouvement.strftime("%d/%m/%Y")
    _recalculer_statut(article)

    db.session.add(entree)
    _journaliser(
        utilisateur, "entree_stock",
        f"Entrée de {quantite} sur « {article.nom} » ({article.reference}) "
        f"— {entree.type_entree_libelle}.",
    )
    db.session.commit()
    return entree


def add_sortie(article_id, date_mouvement, quantite, type_sortie, utilisateur, *,
                type_document=None, reference=None, motif=None):
    """Enregistre une sortie de stock et met à jour l'article. `type_sortie`
    (voir TYPES_SORTIE) détermine quels champs — tous passés en mots-clés —
    sont réellement utilisés :
      - "mouvement_sortie" : type_document ET reference (n° du document)
        obligatoires — comportement standard, inchangé ;
      - "regularisation" : motif obligatoire (mêmes catégories que pour
        une régularisation d'entrée), réservée aux rôles
        ROLES_REGULARISATION (Administrateur / Gestionnaire de stock) —
        pas de justificatif classique.

    Lève ValueError si l'article est introuvable, si `type_sortie` est
    invalide, si un champ obligatoire pour ce type manque, si le rôle de
    `utilisateur` n'autorise pas une régularisation, si la quantité est
    invalide, ou si le stock disponible est insuffisant (le stock ne peut
    jamais devenir négatif, quel que soit le type)."""
    article = _article_mouvementable(article_id)
    if quantite <= 0:
        raise ValueError("La quantité doit être supérieure à zéro.")
    if quantite > article.quantite:
        raise ValueError(
            f"Stock insuffisant : {article.quantite} disponible(s) pour "
            f"« {article.nom} », {quantite} demandé(s)."
        )
    if type_sortie not in TYPES_SORTIE:
        raise ValueError("Type de sortie invalide.")

    type_document = (type_document or "").strip() or None
    reference = (reference or "").strip() or None
    motif = (motif or "").strip() or None

    if type_sortie == "mouvement_sortie":
        if not type_document:
            raise ValueError("Merci de sélectionner un type de document.")
        if not reference:
            raise ValueError("Merci d'indiquer le n° du document.")
        motif = None
    elif type_sortie == "regularisation":
        if utilisateur is None or utilisateur.role not in ROLES_REGULARISATION:
            raise ValueError(
                "Seuls un Administrateur ou un Gestionnaire de stock peuvent "
                "enregistrer une régularisation."
            )
        if not motif:
            raise ValueError("Merci d'indiquer le motif de la régularisation.")
        type_document = None
        reference = None  # pas de document externe pour une régularisation

    sortie = Sortie(
        article_id=article.id, date=date_mouvement, quantite=quantite,
        type_sortie=type_sortie, type_document=type_document, reference=reference, motif=motif,
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
    _journaliser(
        utilisateur, "sortie_stock",
        f"Sortie de {quantite} sur « {article.nom} » ({article.reference}) "
        f"— {sortie.type_sortie_libelle}.",
    )
    db.session.commit()

    if bascule_en_alerte:
        # Après le commit : un échec d'envoi ne doit pas annuler la
        # sortie (mailer.envoyer_alerte_seuil n'élève jamais d'exception).
        mailer.envoyer_alerte_seuil(article)
    return sortie


# ---------------------------------------------------------------------
# Transferts inter-magasins
# ---------------------------------------------------------------------

def _prochaine_reference_transfert(annee):
    """Prochain numéro de transfert pour `annee`, sous la forme
    "TRF-AAAA-00xx" — compteur remis à zéro chaque année civile. Cherche
    le plus grand suffixe déjà attribué cette année-là (pas un simple
    COUNT(*)) pour rester correct même si un transfert venait un jour à
    être supprimé."""
    prefixe = f"TRF-{annee}-"
    suffixes = [
        int(t.reference[len(prefixe):])
        for t in Transfert.query.filter(Transfert.reference.like(f"{prefixe}%")).all()
    ]
    return f"{prefixe}{(max(suffixes) + 1 if suffixes else 1):04d}"


def transferer_stock(magasin_source_id, magasin_destination_id, article_id, quantite,
                      date_mouvement, utilisateur):
    """Transfère `quantite` unités de l'article `article_id` (doit
    appartenir au magasin source) du magasin source vers le magasin
    destination, en une seule opération atomique :
      - décrémente le stock dans le magasin source, comme une sortie (la
        quantité ne peut jamais devenir négative) ;
      - si l'article (même référence) n'existe pas encore dans le magasin
        destination, le crée (même désignation, même fournisseur habituel,
        seuil d'alerte à 0 par défaut — à ajuster ensuite via
        « Modifier ») ; sinon incrémente sa quantité, comme une entrée ;
      - génère une Sortie (côté source) et une Entree (côté destination)
        portant toutes deux la même référence de transfert
        (TRF-AAAA-00xx), et une ligne Transfert qui les relie pour
        l'historique (voir get_transferts) ;
      - journalise l'opération (voir _journaliser).

    Lève ValueError si un magasin est introuvable, si les deux magasins
    sont identiques, si l'article est introuvable dans le magasin source
    ou y est archivé, si la quantité est invalide ou dépasse le stock
    disponible, ou si un article archivé de même référence bloque déjà
    la place dans le magasin destination (à désarchiver d'abord — même
    logique que _article_mouvementable)."""
    magasin_source = db.session.get(Magasin, magasin_source_id)
    magasin_destination = db.session.get(Magasin, magasin_destination_id)
    if magasin_source is None or magasin_destination is None:
        raise ValueError("Magasin source ou destination introuvable.")
    if magasin_source_id == magasin_destination_id:
        raise ValueError("Le magasin source et le magasin destination doivent être différents.")

    # article_id peut arriver vide (ex. champ de recherche d'article laissé
    # sans sélection explicite — voir includes/article-picker.html) : le
    # traiter explicitement plutôt que de laisser Session.get() gérer une
    # clé primaire NULL (accepté aujourd'hui mais déprécié par SQLAlchemy).
    article_source = db.session.get(Article, article_id) if article_id else None
    if article_source is None or article_source.magasin_id != magasin_source_id:
        raise ValueError("Article introuvable dans le magasin source.")
    if article_source.archive:
        raise ValueError(
            f"L'article « {article_source.nom} » est archivé : aucun mouvement ne peut y être "
            "enregistré. Désarchivez-le d'abord."
        )
    if quantite is None or quantite <= 0:
        raise ValueError("La quantité doit être supérieure à zéro.")
    if quantite > article_source.quantite:
        raise ValueError(
            f"Stock insuffisant : {article_source.quantite} disponible(s) pour "
            f"« {article_source.nom} », {quantite} demandé(s)."
        )

    article_destination = Article.query.filter_by(
        reference=article_source.reference, magasin_id=magasin_destination_id
    ).first()
    if article_destination is not None and article_destination.archive:
        raise ValueError(
            f"L'article « {article_destination.nom} » est archivé dans le magasin "
            f"« {magasin_destination.nom} » : désarchivez-le d'abord pour y recevoir ce transfert."
        )

    reference_transfert = _prochaine_reference_transfert(date_mouvement.year)

    # --- Côté source : comme une sortie ---
    sortie = Sortie(
        article_id=article_source.id, date=date_mouvement, quantite=quantite,
        type_document="Transfert inter-magasin", reference=reference_transfert,
        utilisateur_id=utilisateur.id if utilisateur else None,
    )
    statut_avant = article_source.statut
    article_source.quantite -= quantite
    article_source.dernier_mouvement = date_mouvement.strftime("%d/%m/%Y")
    _recalculer_statut(article_source)
    # Même logique que add_sortie : notifier seulement sur la transition
    # vers "Alerte", pas à chaque transfert tant qu'il y reste.
    bascule_en_alerte = statut_avant != "Alerte" and article_source.statut == "Alerte"
    db.session.add(sortie)

    # --- Côté destination : crée l'article si besoin, comme une entrée ---
    if article_destination is None:
        article_destination = Article(
            nom=article_source.nom, reference=article_source.reference,
            seuil=0, quantite=0, fournisseur_id=article_source.fournisseur_id,
            magasin_id=magasin_destination_id, statut="OK", dernier_mouvement="—",
        )
        db.session.add(article_destination)
        db.session.flush()  # récupère article_destination.id pour l'entrée ci-dessous

    entree = Entree(
        article_id=article_destination.id, date=date_mouvement, quantite=quantite,
        fournisseur_id=None, reference=reference_transfert,
        utilisateur_id=utilisateur.id if utilisateur else None,
    )
    article_destination.quantite += quantite
    article_destination.dernier_mouvement = date_mouvement.strftime("%d/%m/%Y")
    _recalculer_statut(article_destination)
    db.session.add(entree)

    # Flush : récupère sortie.id / entree.id, nécessaires pour la ligne
    # Transfert ci-dessous, sans encore valider — tout doit réussir ou
    # rien : un transfert est une seule opération atomique (un seul commit).
    db.session.flush()

    transfert = Transfert(
        reference=reference_transfert, date=date_mouvement, quantite=quantite,
        magasin_source_id=magasin_source_id, magasin_destination_id=magasin_destination_id,
        article_source_id=article_source.id, article_destination_id=article_destination.id,
        sortie_id=sortie.id, entree_id=entree.id,
        utilisateur_id=utilisateur.id if utilisateur else None,
    )
    db.session.add(transfert)

    _journaliser(
        utilisateur, "transfert_stock",
        f"Transfert {reference_transfert} de {quantite} « {article_source.nom} » "
        f"({article_source.reference}) du magasin « {magasin_source.nom} » "
        f"vers « {magasin_destination.nom} ».",
    )
    db.session.commit()

    if bascule_en_alerte:
        # Après le commit, même précaution que add_sortie : un échec
        # d'envoi ne doit jamais annuler le transfert.
        mailer.envoyer_alerte_seuil(article_source)
    return transfert


def get_transferts():
    """Historique des transferts inter-magasins, du plus récent au plus
    ancien, restreint au périmètre magasin courant (voir _scope_magasin) :
    un Gestionnaire de stock voit les transferts où son magasin est
    source OU destination (ce qu'il a envoyé ET ce qu'il a reçu)."""
    query = Transfert.query
    mode, magasin_id = _scope_magasin()
    if mode == "magasin":
        query = query.filter(sa_or(
            Transfert.magasin_source_id == magasin_id,
            Transfert.magasin_destination_id == magasin_id,
        ))
    elif mode == "aucun":
        query = query.filter(sa_false())
    transferts = query.order_by(Transfert.date.desc(), Transfert.id.desc()).all()
    return [
        {
            "reference": t.reference,
            "date": t.date.strftime("%d/%m/%Y"),
            "date_tri": t.date,
            "id_tri": t.id,
            "article": t.article_source.nom,
            "magasin_source": t.magasin_source.nom,
            "magasin_destination": t.magasin_destination.nom,
            "quantite": t.quantite,
            "utilisateur": t.utilisateur.nom if t.utilisateur else "—",
        }
        for t in transferts
    ]


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


def _resoudre_magasin_pour_role(role, magasin_id):
    """Applique la règle magasin/rôle commune à la création et à la
    modification : un « Gestionnaire de stock » doit être rattaché à un
    magasin existant ; pour un Administrateur ou un Comptable (voir
    ROLES_TOUS_MAGASINS), le rattachement n'a pas de sens et est forcé à
    NULL. Lève ValueError si le rôle est inconnu ou si le magasin d'un
    gestionnaire est absent/introuvable. Retourne le magasin_id à
    enregistrer."""
    if role not in ROLE_CLASSES:
        raise ValueError("Rôle invalide.")
    if role in ROLES_TOUS_MAGASINS:
        return None
    if not magasin_id or db.session.get(Magasin, magasin_id) is None:
        raise ValueError(
            "Merci de sélectionner le magasin de rattachement du gestionnaire de stock."
        )
    return magasin_id


def maj_utilisateur(user_id, nom, role, magasin_id, actif, acteur=None):
    """Modifie le nom, le rôle, le magasin de rattachement et le statut
    actif d'un compte existant. L'identifiant (login) n'est
    volontairement pas modifiable — il sert d'ancre à l'historique et à
    la session. Mêmes règles que add_user pour le couple rôle/magasin
    (voir _resoudre_magasin_pour_role). `acteur` est l'utilisateur qui
    effectue la modification : il ne peut pas se désactiver lui-même
    (garde-fou). Lève ValueError si le compte est introuvable, si le nom
    est vide, si le rôle est invalide, si le magasin d'un gestionnaire
    manque, ou en cas d'auto-désactivation."""
    user = db.session.get(Utilisateur, user_id)
    if user is None:
        raise ValueError("Utilisateur introuvable.")
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("Le nom de l'utilisateur est obligatoire.")
    role = (role or "").strip()
    magasin_id = _resoudre_magasin_pour_role(role, magasin_id)
    actif = bool(actif)
    if acteur is not None and acteur.id == user.id:
        # Garde-fous : un administrateur ne peut ni se désactiver, ni se
        # retirer son propre rôle d'administrateur (il pourrait perdre
        # tout accès aux pages d'administration).
        if not actif:
            raise ValueError("Vous ne pouvez pas désactiver votre propre compte.")
        if user.role == "Administrateur" and role != "Administrateur":
            raise ValueError("Vous ne pouvez pas retirer votre propre rôle d'administrateur.")

    user.nom = nom
    user.role = role
    user.magasin_id = magasin_id
    user.actif = actif
    _journaliser(acteur, "modification_utilisateur",
                 f"Modification du compte « {user.identifiant} » "
                 f"(rôle : {role}, statut : {'actif' if actif else 'désactivé'}).")
    db.session.commit()
    return user


def basculer_statut_utilisateur(user_id, actif, acteur=None):
    """Active ou désactive un compte, sans toucher aux autres champs
    (bouton dédié de la liste des utilisateurs). Même garde-fou
    d'auto-désactivation que maj_utilisateur. Lève ValueError si le
    compte est introuvable ou en cas d'auto-désactivation."""
    user = db.session.get(Utilisateur, user_id)
    if user is None:
        raise ValueError("Utilisateur introuvable.")
    actif = bool(actif)
    if acteur is not None and acteur.id == user.id and not actif:
        raise ValueError("Vous ne pouvez pas désactiver votre propre compte.")

    user.actif = actif
    _journaliser(acteur, "statut_utilisateur",
                 f"Compte « {user.identifiant} » {'activé' if actif else 'désactivé'}.")
    db.session.commit()
    return user


def reinitialiser_mot_de_passe(user_id, nouveau, confirmation, acteur=None):
    """Définit un nouveau mot de passe pour un compte existant (action
    d'administration, distincte de maj_utilisateur). Mêmes règles que la
    création : au moins 8 caractères et confirmation identique. La
    session en cours de l'utilisateur ciblé n'est pas invalidée (Flask
    utilise des sessions côté client) : le nouveau mot de passe
    s'applique à la prochaine connexion. Journalisé sans jamais écrire le
    mot de passe. Lève ValueError si le compte est introuvable, si le
    mot de passe est trop court ou si la confirmation ne correspond
    pas."""
    user = db.session.get(Utilisateur, user_id)
    if user is None:
        raise ValueError("Utilisateur introuvable.")
    nouveau = nouveau or ""
    if len(nouveau) < 8:
        raise ValueError("Le mot de passe doit contenir au moins 8 caractères.")
    if nouveau != (confirmation or ""):
        raise ValueError("La confirmation du mot de passe ne correspond pas.")

    user.set_password(nouveau)
    _journaliser(acteur, "reinit_mot_de_passe",
                 f"Réinitialisation du mot de passe du compte « {user.identifiant} ».")
    db.session.commit()
    return user
