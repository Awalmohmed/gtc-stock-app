# -*- encoding: utf-8 -*-
"""
GTC Stock — Données d'exemple (en mémoire, pas de base de données).

Ce module centralise les données factices utilisées par les pages
"métier" de GTC Stock (tableau de bord, entrées/sorties, fiches de
stock, rapprochement Sage 100, alertes, utilisateurs) afin que les
mêmes articles/chiffres restent cohérents d'une page à l'autre.

A terme, ces listes seront remplacées par de vraies requêtes vers une
base de données (voir apps/config.py et flask-sqlalchemy déjà présent
dans requirements.txt).
"""

from werkzeug.security import generate_password_hash, check_password_hash

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
# NOTE — prototype sans base de données : les mots de passe sont
# hachés (werkzeug.security) et gardés en mémoire ici. Mots de passe
# de démonstration ci-dessous ; à remplacer par une vraie table
# "users" (flask-sqlalchemy) le jour où une base est branchée.
#   j.dupont  -> Dupont@2026
#   m.kouam   -> Kouam@2026
#   p.meka    -> Meka@2026
#   s.nkolo   -> compte désactivé (connexion bloquée quel que soit le mot de passe)
# ---------------------------------------------------------------------
ROLE_CLASSES = {
    "Gestionnaire de stock": "primary",
    "Comptable": "info",
    "Administrateur": "dark",
}

UTILISATEURS = [
    {"nom": "Jean Dupont", "identifiant": "j.dupont", "role": "Gestionnaire de stock",
     "role_classe": "primary", "statut": "Actif", "derniere_connexion": "24/08/2026 — 08:03",
     "mot_de_passe_hash": generate_password_hash("Dupont@2026")},
    {"nom": "Marie Kouam", "identifiant": "m.kouam", "role": "Comptable",
     "role_classe": "info", "statut": "Actif", "derniere_connexion": "23/08/2026 — 17:45",
     "mot_de_passe_hash": generate_password_hash("Kouam@2026")},
    {"nom": "Paul Meka", "identifiant": "p.meka", "role": "Administrateur",
     "role_classe": "dark", "statut": "Actif", "derniere_connexion": "24/08/2026 — 07:00",
     "mot_de_passe_hash": generate_password_hash("Meka@2026")},
    {"nom": "Sara Nkolo", "identifiant": "s.nkolo", "role": "Gestionnaire de stock",
     "role_classe": "primary", "statut": "Désactivé", "derniere_connexion": "02/06/2026 — 11:20",
     "mot_de_passe_hash": generate_password_hash("Nkolo@2026")},
]


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


def get_historique(article_id):
    """Historique des mouvements pour un article donné (liste vide si aucun)."""
    return HISTORIQUE.get(article_id, [])


def get_user_by_identifiant(identifiant):
    """Retourne l'utilisateur correspondant à l'identifiant, ou None."""
    for user in UTILISATEURS:
        if user["identifiant"] == identifiant:
            return user
    return None


def verify_credentials(identifiant, mot_de_passe):
    """Vérifie identifiant/mot de passe. Retourne l'utilisateur si valide
    et actif, sinon None (compte inconnu, désactivé ou mot de passe faux)."""
    user = get_user_by_identifiant(identifiant)
    if not user or user["statut"] != "Actif":
        return None
    if not check_password_hash(user["mot_de_passe_hash"], mot_de_passe):
        return None
    return user


def add_user(nom, identifiant, role, mot_de_passe):
    """Crée un nouvel utilisateur en mémoire. Lève ValueError si
    l'identifiant existe déjà."""
    if get_user_by_identifiant(identifiant):
        raise ValueError("Cet identifiant existe déjà.")
    user = {
        "nom": nom,
        "identifiant": identifiant,
        "role": role,
        "role_classe": ROLE_CLASSES.get(role, "secondary"),
        "statut": "Actif",
        "derniere_connexion": "—",
        "mot_de_passe_hash": generate_password_hash(mot_de_passe),
    }
    UTILISATEURS.append(user)
    return user
