# -*- encoding: utf-8 -*-
"""
GTC Stock — Modèles de base de données (SQLAlchemy).
"""

from werkzeug.security import generate_password_hash, check_password_hash

from apps import db

# Classe Bootstrap associée à chaque rôle, pour l'affichage des badges.
ROLE_CLASSES = {
    "Gestionnaire de stock": "primary",
    "Comptable": "info",
    "Administrateur": "dark",
}

# Rôles qui voient tous les magasins (pas de filtrage) plutôt qu'un seul
# magasin_id qui leur est propre — voir apps/gtc_data.py, magasin_effectif().
ROLES_TOUS_MAGASINS = ("Administrateur", "Comptable")


class Magasin(db.Model):
    """Point de vente / entrepôt GTC Stock. Un "Gestionnaire de stock"
    est rattaché à un seul magasin et n'en voit que les articles ; un
    "Administrateur" ou un "Comptable" voit tous les magasins (voir
    ROLES_TOUS_MAGASINS)."""

    __tablename__ = "magasins"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), unique=True, nullable=False, index=True)
    adresse = db.Column(db.String(255), nullable=True)
    # Adresse à laquelle sont envoyés les e-mails d'alerte de stock des
    # articles de ce magasin (voir apps/mailer.py). Peut pointer vers la
    # boîte du gestionnaire ou une liste de diffusion. Vide => on se
    # rabat sur ALERTE_EMAIL_DEFAUT, sinon l'alerte est seulement
    # journalisée.
    email_alertes = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<Magasin {self.nom}>"


class Utilisateur(db.Model):
    """Compte utilisateur de l'application GTC Stock."""

    __tablename__ = "utilisateurs"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False)
    # collation="NOCASE" : "j.dupont" et "J.Dupont" sont traités comme le
    # même identifiant par SQLite (comparaisons, index unique, tri) — évite
    # les doublons de casse et rend la connexion insensible à la casse.
    identifiant = db.Column(db.String(80, collation="NOCASE"), unique=True, nullable=False, index=True)
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    actif = db.Column(db.Boolean, nullable=False, default=True)
    derniere_connexion = db.Column(db.String(50), nullable=True, default="—")
    # Magasin de rattachement — utile seulement pour "Gestionnaire de
    # stock" (voir ROLES_TOUS_MAGASINS) ; NULL pour Administrateur/Comptable.
    magasin_id = db.Column(db.Integer, db.ForeignKey("magasins.id"), nullable=True)

    magasin = db.relationship("Magasin", backref="utilisateurs")

    def __repr__(self):
        return f"<Utilisateur {self.identifiant}>"

    # -- Statut / rôle : dérivés, pour rester compatibles avec les
    #    templates existants (u.statut, u.role_classe).
    @property
    def statut(self):
        return "Actif" if self.actif else "Désactivé"

    @property
    def role_classe(self):
        return ROLE_CLASSES.get(self.role, "secondary")

    # -- Mot de passe
    def set_password(self, mot_de_passe):
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def check_password(self, mot_de_passe):
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)


class TentativeConnexion(db.Model):
    """Compteur de tentatives de connexion échouées, pour le
    rate-limiting de /accounts/sign-in/ (voir apps/rate_limit.py).

    Une ligne par "clé" surveillée (ex. "id:p.meka" ou "ip:203.0.113.5") :
    on limite à la fois par identifiant visé (protège un compte donné du
    brute-force, quelle que soit l'IP) et par IP (protège contre le
    balayage de plusieurs identifiants depuis une même source). Stocké en
    base plutôt qu'en mémoire du process pour rester correct avec
    plusieurs workers gunicorn ou après un redémarrage.
    """

    __tablename__ = "tentatives_connexion"

    id = db.Column(db.Integer, primary_key=True)
    cle = db.Column(db.String(160), unique=True, nullable=False, index=True)
    echecs = db.Column(db.Integer, nullable=False, default=0)
    bloque_jusqua = db.Column(db.DateTime, nullable=True)
    derniere_tentative = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<TentativeConnexion {self.cle} echecs={self.echecs}>"


class Fournisseur(db.Model):
    """Fournisseur associé aux entrées de stock (voir Entree.fournisseur_id
    et la page /pages/fournisseurs/)."""

    __tablename__ = "fournisseurs"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), unique=True, nullable=False, index=True)
    contact = db.Column(db.String(150), nullable=True)

    def __repr__(self):
        return f"<Fournisseur {self.nom}>"


class Article(db.Model):
    """Article suivi en stock."""

    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False)
    reference = db.Column(db.String(50), unique=True, nullable=False, index=True)
    quantite = db.Column(db.Integer, nullable=False, default=0)
    seuil = db.Column(db.Integer, nullable=False, default=0)
    # "Alerte" / "OK" / "Dormant" — mis à jour automatiquement (Alerte/OK)
    # à chaque nouveau mouvement selon quantite vs seuil ; "Dormant" reste
    # tel quel tant qu'aucun mouvement ne survient sur l'article.
    statut = db.Column(db.String(20), nullable=False, default="OK")
    # Dernière quantité connue côté Sage 100, pour le calcul de l'écart
    # (voir la propriété ecart) — alimenté par le rapprochement Sage 100,
    # pas encore automatique (voir apps/sage_connector.py).
    sage_quantite = db.Column(db.Integer, nullable=True)
    dernier_mouvement = db.Column(db.String(20), nullable=True, default="—")
    # Fournisseur habituel/par défaut de cet article (catalogue) — distinct
    # du fournisseur d'une livraison précise (voir Entree.fournisseur_id).
    # Alimenté notamment par l'import de fichier (apps/import_articles.py).
    fournisseur_id = db.Column(db.Integer, db.ForeignKey("fournisseurs.id"), nullable=True)
    # Magasin auquel appartient cet article — un article sans magasin
    # (NULL) n'est visible que par un Administrateur, tant que personne
    # ne le lui a assigné (voir apps/gtc_data.py, magasin_effectif()).
    magasin_id = db.Column(db.Integer, db.ForeignKey("magasins.id"), nullable=True)

    entrees = db.relationship("Entree", backref="article", lazy="dynamic")
    sorties = db.relationship("Sortie", backref="article", lazy="dynamic")
    fournisseur = db.relationship("Fournisseur")
    magasin = db.relationship("Magasin", backref="articles")

    def __repr__(self):
        return f"<Article {self.reference}>"

    @property
    def statut_classe(self):
        """Classe CSS du badge de statut ('alerte' / 'ok' / 'dormant')."""
        return self.statut.lower()

    @property
    def ecart(self):
        """Écart quantité application / Sage 100 (0 si Sage inconnu)."""
        if self.sage_quantite is None:
            return 0
        return self.quantite - self.sage_quantite


class Entree(db.Model):
    """Entrée de stock (réception fournisseur)."""

    __tablename__ = "entrees"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    fournisseur_id = db.Column(db.Integer, db.ForeignKey("fournisseurs.id"), nullable=True)
    reference = db.Column(db.String(50), nullable=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=True)

    utilisateur = db.relationship("Utilisateur")
    fournisseur = db.relationship("Fournisseur")

    def __repr__(self):
        return f"<Entree article={self.article_id} +{self.quantite}>"


class Sortie(db.Model):
    """Sortie de stock (livraison/consommation)."""

    __tablename__ = "sorties"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    type_document = db.Column(db.String(50), nullable=True)
    reference = db.Column(db.String(50), nullable=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=True)

    utilisateur = db.relationship("Utilisateur")

    def __repr__(self):
        return f"<Sortie article={self.article_id} -{self.quantite}>"


# Libellé + classe Bootstrap affichés pour chaque type d'action du
# journal d'activité (voir JournalActivite ci-dessous).
ACTIONS_JOURNAL = {
    "connexion": ("Connexion", "info"),
    "creation_utilisateur": ("Création utilisateur", "dark"),
    "modification_utilisateur": ("Modification utilisateur", "dark"),
    "statut_utilisateur": ("Activation / désactivation", "secondary"),
    "reinit_mot_de_passe": ("Réinitialisation mot de passe", "warning"),
    "entree_stock": ("Entrée de stock", "success"),
    "sortie_stock": ("Sortie de stock", "danger"),
}


class JournalActivite(db.Model):
    """Journal d'activité (audit log) : qui a fait quelle action et
    quand — connexions réussies, créations de comptes utilisateurs,
    mouvements de stock (voir apps/gtc_data.py, fonction _journaliser).
    Page de consultation réservée aux administrateurs
    (/pages/journal/)."""

    __tablename__ = "journal_activite"

    id = db.Column(db.Integer, primary_key=True)
    horodatage = db.Column(db.DateTime, nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=True)
    # Copie de l'identifiant au moment de l'action : reste lisible même
    # si le compte utilisateur est un jour supprimé (pas de fonctionnalité
    # de suppression aujourd'hui, mais l'historique doit rester exploitable).
    identifiant = db.Column(db.String(80), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)

    utilisateur = db.relationship("Utilisateur")

    def __repr__(self):
        return f"<JournalActivite {self.action} par {self.identifiant}>"

    @property
    def action_libelle(self):
        return ACTIONS_JOURNAL.get(self.action, (self.action, "secondary"))[0]

    @property
    def action_classe(self):
        return ACTIONS_JOURNAL.get(self.action, (self.action, "secondary"))[1]
