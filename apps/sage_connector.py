# -*- encoding: utf-8 -*-
"""
GTC Stock — Connecteur Sage 100 (lecture seule, rapprochement de stock).

Se connecte à la base Sage 100 en ODBC (compatible SQL Server comme
Pervasive/Actian PSQL — le driver installé sur le serveur détermine le
moteur réellement utilisé, pas ce module) et lit les quantités en stock
pour les comparer à celles de GTC Stock.

Configuration (variables d'environnement, voir apps/config.py) :
  - SAGE_DB_CONNECTION_STRING
  - SAGE_STOCK_QUERY

Tant que ces deux variables ne sont pas renseignées, is_configured()
renvoie False : apps/gtc_data.py continue alors d'utiliser les données
de démonstration (voir RAPPROCHEMENT) plutôt que de faire croire à une
connexion active. pyodbc n'est importé qu'à l'usage (pas au chargement
du module), pour que l'absence du paquet ou du driver ODBC système ne
casse pas le reste de l'application tant que le rapprochement Sage
n'est pas sollicité.
"""

from apps import app


class SageConnectorError(Exception):
    """Erreur lors de la lecture des quantités Sage 100 (connexion, requête
    SQL invalide, driver ODBC absent du serveur...)."""


def is_configured():
    """True si les deux variables de connexion Sage 100 sont renseignées."""
    return bool(app.config.get('SAGE_DB_CONNECTION_STRING') and app.config.get('SAGE_STOCK_QUERY'))


def get_quantites_sage():
    """Retourne {reference_article: quantite} lues depuis Sage 100.

    Lève SageConnectorError si la connexion n'est pas configurée, si le
    module pyodbc ou le driver ODBC système est absent, si la connexion
    échoue, ou si SAGE_STOCK_QUERY est invalide pour le schéma réel de la
    base Sage 100 de l'entreprise (à adapter, voir apps/config.py)."""
    if not is_configured():
        raise SageConnectorError(
            "Connexion Sage 100 non configurée (SAGE_DB_CONNECTION_STRING "
            "et/ou SAGE_STOCK_QUERY absents)."
        )

    try:
        import pyodbc
    except ImportError as exc:
        raise SageConnectorError(
            "Le module pyodbc n'est pas installé, ou le driver ODBC "
            "système (ex. unixODBC + driver Sage/SQL Server) est absent "
            "du serveur."
        ) from exc

    try:
        with pyodbc.connect(app.config['SAGE_DB_CONNECTION_STRING'], timeout=5) as conn:
            cur = conn.cursor()
            cur.execute(app.config['SAGE_STOCK_QUERY'])
            return {str(reference).strip(): int(quantite) for reference, quantite in cur.fetchall()}
    except pyodbc.Error as exc:
        raise SageConnectorError(f"Échec de la lecture Sage 100 : {exc}") from exc
