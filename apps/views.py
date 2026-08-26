# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

# Flask modules
from flask   import render_template, request, redirect, url_for, session, flash
from jinja2  import TemplateNotFound

# App modules
from apps import app
from apps.gtc_data import (
  ARTICLES, MOUVEMENTS, RAPPROCHEMENT, ALERTES,
  get_stats, get_article, get_historique, get_all_users,
  verify_credentials, add_user, get_user_by_identifiant,
)
from apps.models import ROLE_CLASSES
from apps.auth import login_required, admin_required, is_safe_next_url
from apps.rate_limit import secondes_avant_deblocage, enregistrer_echec, reinitialiser

# App main route -- redirige vers le tableau de bord GTC Stock
@app.route('/')
def index():
  return redirect(url_for('pages_dashboard'))

# Pages -- Dashboard
@app.route('/pages/dashboard/')
@login_required
def pages_dashboard():
  return render_template('pages/dashboard/dashboard.html', segment='dashboard', parent='pages',
                          stats=get_stats(), articles=ARTICLES)

# Pages -- GTC Stock

@app.route('/pages/entrees-sorties/')
@login_required
def pages_entrees_sorties():
  return render_template('pages/entrees_sorties.html', segment='entrees_sorties', parent='pages',
                          articles=ARTICLES, mouvements=MOUVEMENTS)

@app.route('/pages/fiche-stock/')
@login_required
def pages_fiche_stock():
  article_id = request.args.get('article', type=int)
  article = get_article(article_id) or ARTICLES[0]
  return render_template('pages/fiche_stock.html', segment='fiche_stock', parent='pages',
                          articles=ARTICLES, article=article, historique=get_historique(article['id']))

@app.route('/pages/rapprochement/')
@login_required
def pages_rapprochement():
  return render_template('pages/rapprochement.html', segment='rapprochement', parent='pages',
                          rapprochement=RAPPROCHEMENT)

@app.route('/pages/alertes/')
@login_required
def pages_alertes():
  return render_template('pages/alertes.html', segment='alertes', parent='pages',
                          alertes=ALERTES)

@app.route('/pages/utilisateurs/')
@login_required
def pages_utilisateurs():
  return render_template('pages/utilisateurs.html', segment='utilisateurs', parent='pages',
                          utilisateurs=get_all_users())

# Pages

@app.route('/pages/transactions/')
@login_required
def pages_transactions():
  return render_template('pages/transactions.html', segment='transactions', parent='pages')

@app.route('/pages/settings/')
@login_required
def pages_settings():
  return render_template('pages/settings.html', segment='settings', parent='pages')

@app.route('/pages/upgrade-to-pro/')
@login_required
def pages_upgrade_to_pro():
  return render_template('pages/upgrade-to-pro.html', segment='upgrade_to_pro', parent='pages')

# Pages -- Tables

@app.route('/pages/tables/bootstrap-tables/')
@login_required
def pages_tables_bootstrap_tables():
  return render_template('pages/tables/bootstrap-tables.html', segment='bootstrap_tables', parent='tables')

# Pages -- Pages examples

@app.route('/pages/examples/404/')
def pages_examples_404():
  return render_template('pages/examples/404.html', segment='404', parent='pages')

@app.route('/pages/examples/500/')
def pages_examples_500():
  return render_template('pages/examples/500.html', segment='500', parent='pages')

# Accounts

@app.route('/accounts/sign-in/', methods=['GET', 'POST'])
def accounts_sign_in():
  if request.method == 'POST':
    identifiant = (request.form.get('identifiant') or '').strip()
    mot_de_passe = request.form.get('mot_de_passe') or ''

    # Rate-limiting anti brute-force : une clé par identifiant visé (protège
    # ce compte quelle que soit l'IP) et une par IP (protège contre le
    # balayage de plusieurs identifiants depuis une même source).
    cle_identifiant = f"id:{identifiant.lower()}"
    cle_ip = f"ip:{request.remote_addr or 'inconnue'}"
    attente = max(secondes_avant_deblocage(cle_identifiant), secondes_avant_deblocage(cle_ip))
    if attente > 0:
      minutes = max(1, (attente + 59) // 60)
      flash(f"Trop de tentatives de connexion. Réessayez dans {minutes} minute(s).", "danger")
      return render_template('accounts/sign-in.html', segment='sign_in', parent='accounts', stats=get_stats())

    user = verify_credentials(identifiant, mot_de_passe)
    if user:
      reinitialiser(cle_identifiant)
      reinitialiser(cle_ip)
      session.clear()
      session['identifiant'] = user.identifiant
      session['nom'] = user.nom
      session['role'] = user.role
      next_url = request.args.get('next') or request.form.get('next')
      if not is_safe_next_url(next_url):
        next_url = None
      return redirect(next_url or url_for('pages_dashboard'))

    enregistrer_echec(cle_identifiant)
    enregistrer_echec(cle_ip)
    flash("Identifiant ou mot de passe incorrect.", "danger")
  return render_template('accounts/sign-in.html', segment='sign_in', parent='accounts', stats=get_stats())

@app.route('/accounts/sign-up/', methods=['GET', 'POST'])
@admin_required
def accounts_sign_up():
  if request.method == 'POST':
    nom = (request.form.get('nom') or '').strip()
    prenom = (request.form.get('prenom') or '').strip()
    identifiant = (request.form.get('identifiant') or '').strip()
    role = request.form.get('role') or ''
    mot_de_passe = request.form.get('mot_de_passe') or ''
    mot_de_passe_confirmation = request.form.get('mot_de_passe_confirmation') or ''

    erreur = None
    if not (nom and identifiant and role and mot_de_passe):
      erreur = "Merci de renseigner tous les champs obligatoires."
    elif role not in ROLE_CLASSES:
      erreur = "Rôle invalide."
    elif mot_de_passe != mot_de_passe_confirmation:
      erreur = "La confirmation du mot de passe ne correspond pas."
    elif len(mot_de_passe) < 8:
      erreur = "Le mot de passe doit contenir au moins 8 caractères."
    elif get_user_by_identifiant(identifiant):
      erreur = "Cet identifiant existe déjà."

    if erreur:
      flash(erreur, "danger")
      return render_template('accounts/sign-up.html', segment='sign_up', parent='accounts')

    nom_complet = f"{prenom} {nom}".strip()
    try:
      add_user(nom_complet, identifiant, role, mot_de_passe)
    except ValueError as e:
      flash(str(e), "danger")
      return render_template('accounts/sign-up.html', segment='sign_up', parent='accounts')
    flash(f"Compte « {identifiant} » créé avec succès.", "success")
    return redirect(url_for('pages_utilisateurs'))

  return render_template('accounts/sign-up.html', segment='sign_up', parent='accounts')

@app.route('/accounts/logout/')
def accounts_logout():
  session.clear()
  flash("Vous avez été déconnecté.", "info")
  return redirect(url_for('accounts_sign_in'))

@app.route('/accounts/forgot-password/')
def accounts_forgot_password():
  return render_template('accounts/forgot-password.html', segment='forgot_password', parent='accounts')

@app.route('/accounts/reset-password/')
def accounts_reset_password():
  return render_template('accounts/reset-password.html', segment='reset_password', parent='accounts')

@app.route('/accounts/lock/')
def accounts_lock():
  return render_template('accounts/lock.html', segment='lock', parent='accounts')

@app.route('/accounts/password-change/')
def accounts_password_change():
  return render_template('accounts/password-change.html', segment='password-change', parent='accounts')

# Pages Components

@app.route('/pages/components/buttons/')
def pages_components_buttons():
  return render_template('pages/components/buttons.html', segment='buttons', parent='components')

@app.route('/pages/components/notifications/')
def pages_components_notifications():
  return render_template('pages/components/notifications.html', segment='notifications', parent='components')

@app.route('/pages/components/forms/')
def pages_components_forms():
  return render_template('pages/components/forms.html', segment='forms', parent='components')

@app.route('/pages/components/modals/')
def pages_components_modals():
  return render_template('pages/components/modals.html', segment='modals', parent='components')

@app.route('/pages/components/typography/')
def pages_components_typography():
  return render_template('pages/components/typography.html', segment='typography', parent='components')
