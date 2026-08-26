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
    # cross-site, et réservés à HTTPS dès que l'app ne tourne plus en debug
    # (ex. Render, qui sert l'app en TLS).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = not DEBUG

    # Database — SQLite en local par défaut, surchargeable via DATABASE_URL
    # (ex. Postgres en production).
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(project_root, 'gtc_stock.sqlite3')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
