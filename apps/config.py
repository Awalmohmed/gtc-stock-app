# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os

from dotenv import load_dotenv

# Charge les variables d'environnement depuis le fichier .env à la racine du
# projet, s'il existe (chemin explicite plutôt qu'une recherche relative au
# répertoire de travail courant, pour que ça marche pareil qu'on lance
# `python run.py` depuis la racine ou via gunicorn/un service). N'écrase
# jamais une variable déjà présente dans l'environnement réel (override=False
# par défaut) : en production (ex. Render), les vraies variables d'env
# restent prioritaires sur un éventuel .env embarqué par erreur.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))


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

    # Taille max d'un fichier envoyé par l'utilisateur (ex. import
    # d'articles, voir apps/import_articles.py) — évite qu'un fichier
    # énorme (ou malveillant) sature la mémoire du serveur.
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 Mo

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

    # E-mails d'alerte de stock (voir apps/mailer.py) — envoyés à
    # l'adresse du magasin de l'article (Magasin.email_alertes) quand une
    # sortie fait passer cet article sous son seuil. Si SMTP_HOST n'est
    # pas renseigné, l'alerte est seulement écrite dans les logs (l'app
    # ne plante jamais), même logique que le connecteur Sage 100.
    SMTP_HOST = os.getenv('SMTP_HOST')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    SMTP_USE_TLS = (os.getenv('SMTP_USE_TLS', 'True') == 'True')
    # Expéditeur affiché et adresse de repli si un magasin n'a pas
    # d'adresse d'alerte propre.
    ALERTE_EMAIL_EXPEDITEUR = os.getenv('ALERTE_EMAIL_EXPEDITEUR', 'alertes-stock@gtc.local')
    ALERTE_EMAIL_DEFAUT = os.getenv('ALERTE_EMAIL_DEFAUT')

    # Photos de profil (voir apps/avatars.py) — enregistrées directement
    # dans le dossier static, servies comme n'importe quel autre asset.
    # Surchargeable via AVATARS_UPLOAD_DIR pour pointer vers un volume
    # persistant en production (ex. Render/Docker, comme DATABASE_URL
    # ci-dessus) : dans une image reconstruite à chaque déploiement, un
    # fichier écrit sous apps/static/ SANS volume ne survit pas au
    # prochain déploiement.
    AVATARS_UPLOAD_DIR = os.getenv(
        'AVATARS_UPLOAD_DIR',
        os.path.join(basedir, 'static', 'uploads', 'avatars')
    )
