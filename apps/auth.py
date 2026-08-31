# -*- encoding: utf-8 -*-
"""
GTC Stock — Authentification minimale basée sur la session Flask.

Les comptes sont stockés en base (voir apps/models.py, table
"utilisateurs"). Ce module gère uniquement la session Flask qui
matérialise la connexion : décorateurs login_required / admin_required,
et accès à l'utilisateur courant depuis les templates.
"""

from functools import wraps
from urllib.parse import urlparse, urljoin

from flask import session, redirect, url_for, flash, request

from apps import app


def is_safe_next_url(target):
    """Vérifie que `target` est une URL locale (même origine), pour éviter
    les redirections ouvertes (open redirect) via le paramètre `next`."""
    if not target:
        return False
    # Un backslash dans le chemin (ex. "/\evil.com") passe le test de
    # netloc ci-dessous (urlparse ne le traite pas comme un séparateur),
    # mais Werkzeug le renvoie tel quel dans l'en-tête Location, et les
    # navigateurs (spec WHATWG URL) le normalisent en "//evil.com" —
    # une URL protocol-relative qui redirige bien hors du site. On
    # rejette donc tout `target` contenant un backslash, par précaution.
    if '\\' in target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and test_url.netloc == ref_url.netloc


def _current_full_path():
    """URL relative courante (chemin + query string), sûre par construction
    puisque dérivée de la requête entrante elle-même."""
    if request.query_string:
        return f"{request.path}?{request.query_string.decode()}"
    return request.path


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
            return redirect(url_for('accounts_sign_in', next=_current_full_path()))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """Exige une session active avec le rôle Administrateur."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'identifiant' not in session:
            flash("Veuillez vous connecter pour accéder à cette page.", "warning")
            return redirect(url_for('accounts_sign_in', next=_current_full_path()))
        if session.get('role') != 'Administrateur':
            flash("Cette page est réservée aux administrateurs.", "danger")
            return redirect(url_for('pages_dashboard'))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    """Exige une session active dont le rôle fait partie de `roles`
    (ex. gestion du catalogue d'articles : Gestionnaire de stock ou
    Administrateur, mais pas Comptable)."""
    def decorateur(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if 'identifiant' not in session:
                flash("Veuillez vous connecter pour accéder à cette page.", "warning")
                return redirect(url_for('accounts_sign_in', next=_current_full_path()))
            if session.get('role') not in roles:
                flash("Vous n'avez pas les droits pour effectuer cette action.", "danger")
                return redirect(url_for('pages_dashboard'))
            return view(*args, **kwargs)
        return wrapped
    return decorateur


@app.context_processor
def inject_current_user():
    """Rend `current_user` disponible dans tous les templates sans avoir
    à le passer explicitement depuis chaque route."""
    return {'current_user': current_user()}
