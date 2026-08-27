# -*- encoding: utf-8 -*-
"""
GTC Stock — Données d'exemple et accès aux données.

Les articles, mouvements, rapprochements et alertes ci-dessous restent
des données factices en mémoire (pas encore de base de données pour
ces objets métier). En revanche, les comptes utilisateurs sont
désormais stockés dans une vraie base SQLite via SQLAlchemy
(voir apps/models.py et apps/config.py) — les fonctions
get_user_by_identifiant, verify_credentials et add_user interrogent la
table "utilisateurs".
"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from apps import db
from apps.models import Utilisateur
from apps import sage_connector

# ---------------------------------------------------------------------
# Articles suivis en stock
# ---------------------------------------------------------------------
ARTICLES = [
    {
        "id": 1,
        "nom": "Rame de papier A4",
        "reference": "REF-0021",
        "quantite": 5,
        "seuil": 10,
        "statut": "Alerte",
        "statut_classe": "alerte",
        "sage_quantite": 5,
        "ecart": 0,
        "dernier_mouvement": "22/08/2026",
    },
    {
        "id": 2,
        "nom": "Cartouche imprimante",
        "reference": "REF-0045",
        "quantite": 50,
        "seuil": 20,
        "statut": "OK",
        "statut_classe": "ok",
        "sage_quantite": 50,
        "ecart": 0,
        "dernier_mouvement": "20/08/2026",
    },
    {
        "id": 3,
        "nom": "Classeur A4",
        "reference": "REF-0102",
        "quantite": 8,
        "seuil": 15,
        "statut": "Alerte",
        "statut_classe": "alerte",
        "sage_quantite": 11,
        "ecart": -3,
        "dernier_mouvement": "21/08/2026",
    },
    {
        "id": 4,
        "nom": "Chaise bureau (modèle X)",
        "reference": "REF-0230",
        "quantite": 14,
        "seuil": 2,
        "statut": "Dormant",
        "statut_classe": "dormant",
        "sage_quantite": 14,
        "ecart": 0,
        "dernier_mouvement": "—",
    },
    {
        "id": 5,
        "nom": "Stylo bille bleu (boîte)",
        "reference": "REF-0011",
        "quantite": 96,
        "seuil": 30,
        "statut": "OK",
        "statut_classe": "ok",
        "sage_quantite": 90,
        "ecart": 6,
        "dernier_mouvement": "18/08/2026",
    },
]

# ---------------------------------------------------------------------
# Derniers mouvements (entrées / sorties)
# ---------------------------------------------------------------------
MOUVEMENTS = [
    {"date": "22/08/2026", "article": "Rame de papier A4", "type": "Entrée",
     "reference": "BR-2026-0143", "quantite": "+50", "saisi_par": "J. Dupont"},
    {"date": "21/08/2026", "article": "Classeur A4", "type": "Sortie",
     "reference": "BL-2026-0087", "quantite": "-5", "saisi_par": "J. Dupont"},
    {"date": "20/08/2026", "article": "Cartouche imprimante", "type": "Sortie",
     "reference": "BC-2026-0212", "quantite": "-10", "saisi_par": "J. Dupont"},
]

# ---------------------------------------------------------------------
# Historique détaillé par article, pour la fiche de stock
# ---------------------------------------------------------------------
HISTORIQUE = {
    1: [
        {"date": "22/08/2026", "type": "Sortie", "reference": "BL-2026-0090", "quantite": "-15", "solde": 5},
        {"date": "10/08/2026", "type": "Entrée", "reference": "BR-2026-0110", "quantite": "+20", "solde": 20},
        {"date": "28/07/2026", "type": "Sortie", "reference": "BC-2026-0175", "quantite": "-10", "solde": 0},
    ],
    2: [
        {"date": "20/08/2026", "type": "Sortie", "reference": "BC-2026-0212", "quantite": "-10", "solde": 50},
        {"date": "05/08/2026", "type": "Entrée", "reference": "BR-2026-0098", "quantite": "+30", "solde": 60},
    ],
    3: [
        {"date": "21/08/2026", "type": "Sortie", "reference": "BL-2026-0087", "quantite": "-5", "solde": 8},
        {"date": "01/08/2026", "type": "Entrée", "reference": "BR-2026-0075", "quantite": "+13", "solde": 13},
    ],
    4: [
        {"date": "15/05/2026", "type": "Entrée", "reference": "BR-2026-0033", "quantite": "+14", "solde": 14},
    ],
    5: [
        {"date": "18/08/2026", "type": "Sortie", "reference": "BL-2026-0080", "quantite": "-4", "solde": 96},
        {"date": "02/08/2026", "type": "Entrée", "reference": "BR-2026-0091", "quantite": "+40", "solde": 100},
    ],
}

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
    return {
        "total_articles": len(ARTICLES),
        "alertes": sum(1 for a in ARTICLES if a["statut_classe"] == "alerte"),
        "dormants": sum(1 for a in ARTICLES if a["statut_classe"] == "dormant"),
        "ecarts": sum(1 for a in ARTICLES if a["ecart"]),
    }


def get_article(article_id):
    """Retourne l'article correspondant à l'id, ou None si absent/invalide."""
    for article in ARTICLES:
        if article["id"] == article_id:
            return article
    return None


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
    for article in ARTICLES:
        qte_sage = quantites_sage.get(article["reference"])
        if qte_sage is None:
            continue  # article absent de la base Sage : pas de comparaison possible
        ecart = article["quantite"] - qte_sage
        lignes.append({
            "article": article["nom"],
            "qte_app": article["quantite"],
            "qte_sage": qte_sage,
            "ecart": ecart,
            "conforme": ecart == 0,
        })
    return lignes, True, None


def get_historique(article_id):
    """Historique des mouvements pour un article donné (liste vide si aucun)."""
    return HISTORIQUE.get(article_id, [])


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
