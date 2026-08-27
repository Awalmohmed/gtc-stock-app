# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os

# import Flask
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config

# Inject Flask magic
app = Flask(__name__)

# load Configuration
app.config.from_object( Config )

# En production, l'app tourne derrière UN SEUL proxy inverse (l'edge
# Render — voir render.yaml) qui pose X-Forwarded-For/-Proto/-Host. Sans ce
# middleware, request.remote_addr renverrait l'adresse interne du proxy
# pour toutes les requêtes, faussant le rate-limiting par IP (voir
# apps/rate_limit.py) : tout le monde partagerait le même compteur.
# x_for=1 ne fait confiance qu'à ce seul niveau de proxy ; à ajuster si un
# proxy supplémentaire (CDN...) est un jour ajouté devant l'app.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Protection CSRF sur toutes les routes POST/PUT/PATCH/DELETE (formulaires
# de connexion et de création de compte notamment) ; les templates doivent
# inclure {{ csrf_token() }} dans un champ caché.
csrf = CSRFProtect(app)

# Database (SQLAlchemy) + migrations (Flask-Migrate / Alembic)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Import models first so Alembic/Flask-Migrate can detect them
from apps import models

# Import routing to render the pages
from apps import views
