# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os

# import Flask
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from .config import Config

# Inject Flask magic
app = Flask(__name__)

# load Configuration
app.config.from_object( Config )

# Database (SQLAlchemy) + migrations (Flask-Migrate / Alembic)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Import models first so Alembic/Flask-Migrate can detect them
from apps import models

# Import routing to render the pages
from apps import views
