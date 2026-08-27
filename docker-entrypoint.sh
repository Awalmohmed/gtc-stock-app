#!/usr/bin/env bash
# exit on error
set -o errexit

# Applique les migrations (crée/actualise les tables utilisateurs et
# tentatives_connexion — voir migrations/) avant que gunicorn ne démarre.
# Idempotent : ne fait rien si la base est déjà à jour.
flask db upgrade

exec gunicorn --config gunicorn-cfg.py run:app
