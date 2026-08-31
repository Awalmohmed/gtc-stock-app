# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

# Flask modules
from datetime import datetime

from flask   import render_template, request, redirect, url_for, session, flash, Response
from jinja2  import TemplateNotFound

# App modules
from apps import app, db
from apps.gtc_data import (
  get_stats, get_all_articles, get_article, get_historique, get_mouvements,
  add_entree, add_sortie, get_all_users, get_rapprochement,
  get_all_fournisseurs, add_fournisseur, get_journal, get_alertes,
  get_all_magasins, get_magasins_detailles, add_magasin,
  verify_credentials, add_user, get_user_by_identifiant,
)
from apps.models import ROLE_CLASSES, Magasin, ROLES_TOUS_MAGASINS
from apps.auth import login_required, admin_required, is_safe_next_url
from apps.rate_limit import secondes_avant_deblocage, enregistrer_echec, reinitialiser
from apps.import_articles import importer_fichier, modele_csv, FichierInvalide
from apps import exports

# App main route -- redirige vers le tableau de bord GTC Stock
@app.route('/')
def index():
  return redirect(url_for('pages_dashboard'))


@app.context_processor
def injecter_selecteur_magasin():
  """Alimente le sélecteur de magasin de la barre supérieure — visible
  uniquement pour les rôles qui voient tous les magasins (Administrateur,
  Comptable ; voir ROLES_TOUS_MAGASINS). Pour un Gestionnaire de stock,
  rien n'est injecté : il est lié à un seul magasin, sans choix possible."""
  if session.get('role') not in ROLES_TOUS_MAGASINS:
    return {}
  return {
    'magasins_selecteur': get_all_magasins(),
    'magasin_filtre_actif': session.get('magasin_filtre'),
  }


@app.route('/pages/magasin-filtre', methods=['POST'])
@login_required
def definir_magasin_filtre():
  """Enregistre (ou efface) le magasin choisi dans le sélecteur de la
  barre supérieure. Réservé aux rôles qui voient tous les magasins ;
  pour les autres, le périmètre est imposé par leur rattachement."""
  if session.get('role') in ROLES_TOUS_MAGASINS:
    magasin_id = request.form.get('magasin_id', type=int)
    if magasin_id and db.session.get(Magasin, magasin_id):
      session['magasin_filtre'] = magasin_id
    else:
      session.pop('magasin_filtre', None)
  retour = request.form.get('retour')
  if not is_safe_next_url(retour):
    retour = url_for('pages_dashboard')
  return redirect(retour)

# Pages -- Dashboard
@app.route('/pages/dashboard/')
@login_required
def pages_dashboard():
  return render_template('pages/dashboard/dashboard.html', segment='dashboard', parent='pages',
                          stats=get_stats(), articles=get_all_articles())

# Pages -- GTC Stock

@app.route('/pages/entrees-sorties/')
@login_required
def pages_entrees_sorties():
  return render_template('pages/entrees_sorties.html', segment='entrees_sorties', parent='pages',
                          articles=get_all_articles(), mouvements=get_mouvements(),
                          fournisseurs=get_all_fournisseurs())

def _parser_date_formulaire(valeur):
  """Convertit la date d'un <input type="date"> (format AAAA-MM-JJ) en
  objet date Python. Lève ValueError (message utilisateur) si absente/invalide."""
  try:
    return datetime.strptime(valeur, '%Y-%m-%d').date()
  except (TypeError, ValueError):
    raise ValueError("Merci d'indiquer une date valide.")

@app.route('/pages/entrees-sorties/nouvelle-entree', methods=['POST'])
@login_required
def creer_entree():
  utilisateur = get_user_by_identifiant(session.get('identifiant'))
  try:
    article_id = request.form.get('article_id', type=int)
    quantite = request.form.get('quantite', type=int)
    date_mouvement = _parser_date_formulaire(request.form.get('date') or '')
    fournisseur_id = request.form.get('fournisseur_id', type=int)
    reference = (request.form.get('reference') or '').strip()
    if quantite is None:
      raise ValueError("Merci d'indiquer une quantité valide.")
    add_entree(article_id, date_mouvement, quantite, fournisseur_id, reference, utilisateur)
  except ValueError as e:
    flash(str(e), 'danger')
    return redirect(url_for('pages_entrees_sorties'))
  flash("Entrée de stock enregistrée avec succès.", 'success')
  return redirect(url_for('pages_entrees_sorties'))

@app.route('/pages/entrees-sorties/nouvelle-sortie', methods=['POST'])
@login_required
def creer_sortie():
  utilisateur = get_user_by_identifiant(session.get('identifiant'))
  try:
    article_id = request.form.get('article_id', type=int)
    quantite = request.form.get('quantite', type=int)
    date_mouvement = _parser_date_formulaire(request.form.get('date') or '')
    type_document = (request.form.get('type_document') or '').strip()
    reference = (request.form.get('reference') or '').strip()
    if quantite is None:
      raise ValueError("Merci d'indiquer une quantité valide.")
    add_sortie(article_id, date_mouvement, quantite, type_document, reference, utilisateur)
  except ValueError as e:
    flash(str(e), 'danger')
    return redirect(url_for('pages_entrees_sorties'))
  flash("Sortie de stock enregistrée avec succès.", 'success')
  return redirect(url_for('pages_entrees_sorties'))

@app.route('/pages/fiche-stock/')
@login_required
def pages_fiche_stock():
  articles = get_all_articles()
  article_id = request.args.get('article', type=int)
  article = get_article(article_id) or (articles[0] if articles else None)
  historique = get_historique(article.id) if article else []
  return render_template('pages/fiche_stock.html', segment='fiche_stock', parent='pages',
                          articles=articles, article=article, historique=historique)

def _article_courant_ou_404():
  """Article ciblé par ?article=<id> (ou le premier disponible), pour
  les routes d'export — None si aucun article n'existe en base."""
  articles = get_all_articles()
  article_id = request.args.get('article', type=int)
  return get_article(article_id) or (articles[0] if articles else None)

@app.route('/pages/fiche-stock/export.pdf')
@login_required
def export_fiche_stock_pdf():
  article = _article_courant_ou_404()
  if not article:
    flash("Aucun article à exporter.", 'danger')
    return redirect(url_for('pages_fiche_stock'))
  contenu = exports.fiche_stock_pdf(article, get_historique(article.id))
  nom_fichier = f"fiche-stock-{article.reference}.pdf"
  return Response(contenu, mimetype='application/pdf',
                   headers={'Content-Disposition': f'attachment; filename="{nom_fichier}"'})

@app.route('/pages/fiche-stock/export.xlsx')
@login_required
def export_fiche_stock_excel():
  article = _article_courant_ou_404()
  if not article:
    flash("Aucun article à exporter.", 'danger')
    return redirect(url_for('pages_fiche_stock'))
  contenu = exports.fiche_stock_excel(article, get_historique(article.id))
  nom_fichier = f"fiche-stock-{article.reference}.xlsx"
  return Response(contenu, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                   headers={'Content-Disposition': f'attachment; filename="{nom_fichier}"'})

@app.route('/pages/fiche-stock/import', methods=['GET', 'POST'])
@login_required
def import_articles():
  resultat = None
  if request.method == 'POST':
    fichier = request.files.get('fichier')
    if not fichier or not fichier.filename:
      flash("Merci de sélectionner un fichier.", 'danger')
    else:
      try:
        resultat = importer_fichier(fichier.filename, fichier.read())
        if resultat['erreurs']:
          flash(
            f"Import terminé avec des erreurs : {resultat['crees']} créé(s), "
            f"{resultat['maj']} mis à jour, {len(resultat['erreurs'])} ligne(s) rejetée(s).",
            'warning',
          )
        else:
          flash(
            f"Import réussi : {resultat['crees']} article(s) créé(s), "
            f"{resultat['maj']} mis à jour.",
            'success',
          )
      except FichierInvalide as e:
        flash(str(e), 'danger')
  return render_template('pages/import_articles.html', segment='fiche_stock', parent='pages',
                          resultat=resultat)

@app.route('/pages/fiche-stock/import/modele.csv')
@login_required
def import_articles_modele():
  return Response(
    modele_csv(), mimetype='text/csv',
    headers={'Content-Disposition': 'attachment; filename="modele_import_articles.csv"'},
  )

@app.route('/pages/fournisseurs/')
@login_required
def pages_fournisseurs():
  return render_template('pages/fournisseurs.html', segment='fournisseurs', parent='pages',
                          fournisseurs=get_all_fournisseurs())

@app.route('/pages/fournisseurs/nouveau', methods=['POST'])
@login_required
def creer_fournisseur():
  nom = request.form.get('nom') or ''
  contact = request.form.get('contact') or ''
  try:
    add_fournisseur(nom, contact)
  except ValueError as e:
    flash(str(e), 'danger')
    return redirect(url_for('pages_fournisseurs'))
  flash(f"Fournisseur « {nom.strip()} » ajouté avec succès.", 'success')
  return redirect(url_for('pages_fournisseurs'))

@app.route('/pages/rapprochement/')
@login_required
def pages_rapprochement():
  rapprochement, sage_connecte, erreur_sage = get_rapprochement()
  return render_template('pages/rapprochement.html', segment='rapprochement', parent='pages',
                          rapprochement=rapprochement, sage_connecte=sage_connecte, erreur_sage=erreur_sage)

@app.route('/pages/rapprochement/export.pdf')
@login_required
def export_rapprochement_pdf():
  rapprochement, sage_connecte, _erreur = get_rapprochement()
  contenu = exports.rapprochement_pdf(rapprochement, sage_connecte)
  return Response(contenu, mimetype='application/pdf',
                   headers={'Content-Disposition': 'attachment; filename="rapprochement.pdf"'})

@app.route('/pages/rapprochement/export.xlsx')
@login_required
def export_rapprochement_excel():
  rapprochement, sage_connecte, _erreur = get_rapprochement()
  contenu = exports.rapprochement_excel(rapprochement, sage_connecte)
  return Response(contenu, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                   headers={'Content-Disposition': 'attachment; filename="rapprochement.xlsx"'})

@app.route('/pages/alertes/')
@login_required
def pages_alertes():
  return render_template('pages/alertes.html', segment='alertes', parent='pages',
                          alertes=get_alertes())

@app.route('/pages/utilisateurs/')
@login_required
def pages_utilisateurs():
  return render_template('pages/utilisateurs.html', segment='utilisateurs', parent='pages',
                          utilisateurs=get_all_users())

@app.route('/pages/magasins/')
@admin_required
def pages_magasins():
  return render_template('pages/magasins.html', segment='magasins', parent='pages',
                          magasins=get_magasins_detailles())

@app.route('/pages/magasins/nouveau', methods=['POST'])
@admin_required
def creer_magasin():
  nom = request.form.get('nom') or ''
  adresse = request.form.get('adresse') or ''
  try:
    add_magasin(nom, adresse)
  except ValueError as e:
    flash(str(e), 'danger')
    return redirect(url_for('pages_magasins'))
  flash(f"Magasin « {nom.strip()} » ajouté avec succès.", 'success')
  return redirect(url_for('pages_magasins'))

@app.route('/pages/journal/')
@admin_required
def pages_journal():
  return render_template('pages/journal.html', segment='journal', parent='pages',
                          journal=get_journal())

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
      # "Se souvenir de moi" : session persistante (durée définie par
      # PERMANENT_SESSION_LIFETIME, 31 jours par défaut chez Flask) au lieu
      # d'expirer à la fermeture du navigateur.
      session.permanent = bool(request.form.get('remember'))
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
  def afficher_formulaire():
    return render_template('accounts/sign-up.html', segment='sign_up', parent='accounts',
                            magasins=get_all_magasins())

  if request.method == 'POST':
    nom = (request.form.get('nom') or '').strip()
    prenom = (request.form.get('prenom') or '').strip()
    identifiant = (request.form.get('identifiant') or '').strip()
    role = request.form.get('role') or ''
    mot_de_passe = request.form.get('mot_de_passe') or ''
    mot_de_passe_confirmation = request.form.get('mot_de_passe_confirmation') or ''
    magasin_id = request.form.get('magasin_id', type=int)

    # Le magasin de rattachement n'est demandé que pour un Gestionnaire
    # de stock ; pour un Administrateur ou un Comptable (voir
    # ROLES_TOUS_MAGASINS), il est ignoré — ces rôles voient tous les
    # magasins (add_user force alors magasin_id à NULL).
    magasin_obligatoire = role not in ROLES_TOUS_MAGASINS

    erreur = None
    if not (nom and identifiant and role and mot_de_passe):
      erreur = "Merci de renseigner tous les champs obligatoires."
    elif role not in ROLE_CLASSES:
      erreur = "Rôle invalide."
    elif magasin_obligatoire and not (magasin_id and db.session.get(Magasin, magasin_id)):
      erreur = "Merci de sélectionner le magasin de rattachement du gestionnaire de stock."
    elif mot_de_passe != mot_de_passe_confirmation:
      erreur = "La confirmation du mot de passe ne correspond pas."
    elif len(mot_de_passe) < 8:
      erreur = "Le mot de passe doit contenir au moins 8 caractères."
    elif get_user_by_identifiant(identifiant):
      erreur = "Cet identifiant existe déjà."

    if erreur:
      flash(erreur, "danger")
      return afficher_formulaire()

    nom_complet = f"{prenom} {nom}".strip()
    admin_actuel = get_user_by_identifiant(session.get('identifiant'))
    try:
      add_user(nom_complet, identifiant, role, mot_de_passe,
               magasin_id=magasin_id, cree_par=admin_actuel)
    except ValueError as e:
      flash(str(e), "danger")
      return afficher_formulaire()
    flash(f"Compte « {identifiant} » créé avec succès.", "success")
    return redirect(url_for('pages_utilisateurs'))

  return afficher_formulaire()

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
