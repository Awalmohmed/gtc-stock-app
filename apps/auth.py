# -*- encoding: utf-8 -*-
"""
GTC Stock — Authentification minimale basée sur la session Flask.

Prototype sans base de données : les comptes vivent en mémoire dans
apps/gtc_data.py (UTILISATEURS). Suffisant pour protéger les pages et
réserver la création de compte aux administrateurs ; à remplacer par
flask-login + une vraie table "users" le jour où une base est branchée.
"""

from functools import wraps

from flask import session, redirect, url_for, flash, request

from apps import app


def current_user():
    """Infos de session de l'utilisateur connecté, ou None si visiteur."""
    if 'identifiant' not in session:
        return None
    return {
        'identifiant': session['identifiant'],
        'nom': session.get('nom'),
        'role': session.get('role'),
    }


def login_required(view):
    """Exige une session active ; sinon redirige vers la connexion."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'identifiant' not in session:
            flash("Veuillez vous connecter pour accéder à cette page.", "warning")
            return redirect(url_for('accounts_sign_in', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """Exige une session active avec le rôle Administrateur."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'identifiant' not in session:
            flash("Veuillez vous connecter pour accéder à cette page.", "warning")
            return redirect(url_for('accounts_sign_in', next=request.path))
        if session.get('role') != 'Administrateur':
            flash("Cette page est réservée aux administrateurs.", "danger")
            return redirect(url_for('pages_dashboard'))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_current_user():
    """Rend `current_user` disponible dans tous les templates sans avoir
    à le passer explicitement depuis chaque route."""
    return {'current_user': current_user()}
