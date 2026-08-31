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

from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from apps import db
from apps.models import Utilisateur, Article, Entree, Sortie
from apps import sage_connector

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
    """Chiffres agrégés pour les cartes du tableau de bord."""
    articles = Article.query.all()
    return {
        "total_articles": len(articles),
        "alertes": sum(1 for a in articles if a.statut_classe == "alerte"),
        "dormants": sum(1 for a in articles if a.statut_classe == "dormant"),
        "ecarts": sum(1 for a in articles if a.ecart),
    }


def get_all_articles():
    """Retourne tous les articles, triés par nom."""
    return Article.query.order_by(Article.nom).all()


def get_article(article_id):
    """Retourne l'article correspondant à l'id, ou None si absent/invalide."""
    if not article_id:
        return None
    return db.session.get(Article, article_id)


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
        return RAPPROCHEMENT, False, None

    try:
        quantites_sage = sage_connector.get_quantites_sage()
    except sage_connector.SageConnectorError as e:
        return RAPPROCHEMENT, False, str(e)

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
    """Tous les mouvements (entrées + sorties), tous articles confondus,
    du plus récent au plus ancien — pour la page Entrées/Sorties."""
    lignes = [_mouvement_vers_dict(e, "Entrée", "+") for e in Entree.query.all()]
    lignes += [_mouvement_vers_dict(s, "Sortie", "-") for s in Sortie.query.all()]
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


def add_entree(article_id, date_mouvement, quantite, fournisseur, reference, utilisateur):
    """Enregistre une entrée de stock et met à jour l'article. Lève
    ValueError si l'article est introuvable ou la quantité invalide."""
    article = get_article(article_id)
    if not article:
        raise ValueError("Article introuvable.")
    if quantite <= 0:
        raise ValueError("La quantité doit être supérieure à zéro.")

    entree = Entree(
        article_id=article.id, date=date_mouvement, quantite=quantite,
        fournisseur=fournisseur or None, reference=reference or None,
        utilisateur_id=utilisateur.id if utilisateur else None,
    )
    article.quantite += quantite
    article.dernier_mouvement = date_mouvement.strftime("%d/%m/%Y")
    _recalculer_statut(article)

    db.session.add(entree)
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
    article.quantite -= quantite
    article.dernier_mouvement = date_mouvement.strftime("%d/%m/%Y")
    _recalculer_statut(article)

    db.session.add(sortie)
    db.session.commit()
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
    db.session.commit()
    return user


def add_user(nom, identifiant, role, mot_de_passe):
    """Crée un nouvel utilisateur en base. Lève ValueError si
    l'identifiant existe déjà (y compris en cas de double soumission
    quasi simultanée : la contrainte d'unicité en base fait foi, pas
    seulement la vérification préalable)."""
    if get_user_by_identifiant(identifiant):
        raise ValueError("Cet identifiant existe déjà.")
    user = Utilisateur(nom=nom, identifiant=identifiant, role=role, actif=True)
    user.set_password(mot_de_passe)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Cet identifiant existe déjà.")
    return user
