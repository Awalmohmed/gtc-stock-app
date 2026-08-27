#!/usr/bin/env bash
# exit on error
set -o errexit

python -m pip install --upgrade pip

pip install -r requirements.txt

# Applique les migrations (crée/actualise les tables utilisateurs et
# tentatives_connexion — voir migrations/) avant que gunicorn ne démarre.
export FLASK_APP=run.py
flask db upgrade
