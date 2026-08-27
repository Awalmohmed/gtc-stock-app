# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os

class Config(object):

    basedir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.dirname(basedir)

    DEBUG = (os.getenv('DEBUG', 'False') == 'True')

    # Assets Management
    ASSETS_ROOT = os.getenv('ASSETS_ROOT', '/static/assets')

    # App Config - the minimal footprint
    SECRET_KEY = os.getenv('SECRET_KEY', 'S#perS3crEt_9999')

    # Cookies de session : non accessibles en JS, jamais envoyés en
    # cross-site. SESSION_COOKIE_SECURE est piloté explicitement par une
    # variable d'environnement (plutôt que déduit de DEBUG, qui vaut déjà
    # False par défaut en local) : à activer en production derrière HTTPS
    # (ex. Render — voir render.yaml), à laisser désactivé en local sous
    # http:// sous peine de perdre la session juste après connexion.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = (os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True')

    # Database — SQLite en local par défaut, surchargeable via DATABASE_URL
    # (ex. Postgres en production).
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(project_root, 'gtc_stock.sqlite3')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Rapprochement Sage 100 — lecture seule via ODBC (voir
    # apps/sage_connector.py). Compatible aussi bien Sage 100cloud (SQL
    # Server) que Sage 100 Pervasive/Actian PSQL : c'est le driver ODBC
    # installé sur le serveur qui détermine le moteur réellement contacté,
    # pas ce code. Non renseignées par défaut : la page de rapprochement
    # affiche alors les données de démonstration avec un bandeau explicite
    # plutôt que de simuler une connexion active.
    #
    # SAGE_DB_CONNECTION_STRING : chaîne de connexion ODBC complète, ex.
    #   "DRIVER={ODBC Driver 17 for SQL Server};SERVER=...;DATABASE=...;
    #    UID=...;PWD=...;"
    #   ou un DSN déjà déclaré sur le serveur : "DSN=Sage100;UID=...;PWD=..."
    # SAGE_STOCK_QUERY : requête SQL à adapter au schéma réel de la base
    #   Sage 100 de l'entreprise (nom de table/colonnes selon l'édition et
    #   le paramétrage) ; doit retourner exactement 2 colonnes dans cet
    #   ordre : référence article, quantité en stock.
    SAGE_DB_CONNECTION_STRING = os.getenv('SAGE_DB_CONNECTION_STRING')
    SAGE_STOCK_QUERY = os.getenv('SAGE_STOCK_QUERY')
