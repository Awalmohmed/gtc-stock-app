# -*- encoding: utf-8 -*-
"""
GTC Stock — Modèles de base de données (SQLAlchemy).
"""

import sqlalchemy as sa
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
    # Photo de profil : chemin relatif à apps/static/ (ex.
    # "uploads/avatars/3.jpg"), voir apps/avatars.py pour l'upload/la
    # validation. NULL -> avatar par défaut (cercle gris avec initiale)
    # affiché par les templates.
    photo = db.Column(db.String(255), nullable=True)

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
    # Unique seulement PAR MAGASIN (voir __table_args__ ci-dessous) : un
    # même article (même référence, même désignation) peut exister dans
    # plusieurs magasins, chacun avec sa propre quantité — notamment suite
    # à un transfert inter-magasin (voir gtc_data.transferer_stock). index
    # (non unique) conservé pour les recherches par référence seule
    # (import de fichier, rapprochement Sage 100).
    reference = db.Column(db.String(50), nullable=False, index=True)
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
    # Archivage (suppression douce) : un article archivé est conservé en
    # base — avec tout son historique de mouvements — mais retiré de
    # toutes les vues opérationnelles (liste, fiche de stock, saisies,
    # dashboard, alertes, rapprochement) et ne peut plus être mouvementé.
    # Réversible via « désarchiver ». On ne supprime jamais vraiment un
    # article pour préserver l'historique et le rapprochement comptable.
    archive = db.Column(db.Boolean, nullable=False, default=False, server_default=sa.false())
    # Fournisseur habituel/par défaut de cet article (catalogue) — distinct
    # du fournisseur d'une livraison précise (voir Entree.fournisseur_id).
    # Alimenté notamment par l'import de fichier (apps/import_articles.py).
    fournisseur_id = db.Column(db.Integer, db.ForeignKey("fournisseurs.id"), nullable=True)
    # Magasin auquel appartient cet article — un article sans magasin
    # (NULL) n'est visible que par un Administrateur, tant que personne
    # ne le lui a assigné (voir apps/gtc_data.py, magasin_effectif()).
    magasin_id = db.Column(db.Integer, db.ForeignKey("magasins.id"), nullable=True)

    # Un article NULL (sans magasin, cas hérité ci-dessus) n'est pas
    # concerné par cette contrainte : deux magasin_id NULL ne sont jamais
    # considérés comme égaux (sémantique standard SQL), donc pas de
    # conflit d'unicité entre eux — un admin les rattachera un jour à un
    # magasin, à ce moment-là seulement l'unicité s'appliquera vraiment.
    __table_args__ = (
        db.UniqueConstraint('reference', 'magasin_id', name='uq_articles_reference_magasin'),
    )

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


# Libellé + classe Bootstrap affichés pour chaque type d'entrée de stock
# (voir Entree.type_entree ci-dessous et apps/gtc_data.py, add_entree) —
# même principe que ACTIONS_JOURNAL.
TYPES_ENTREE = {
    "reception_fournisseur": ("Réception fournisseur", "success"),
    "retour_client": ("Retour client", "info"),
    "regularisation": ("Régularisation", "warning"),
}

# La régularisation modifie le stock sans document externe réel (pas de
# bordereau, pas de client) : réservée aux rôles opérationnels, pas à un
# Comptable (qui peut, lui, toujours saisir une réception ou un retour
# client — voir apps/gtc_data.py, add_entree).
ROLES_REGULARISATION = ("Administrateur", "Gestionnaire de stock")


class Entree(db.Model):
    """Entrée de stock : réception fournisseur, retour client, ou
    régularisation de stock (voir TYPES_ENTREE). Champs utilisés selon
    le type (voir apps/gtc_data.py, add_entree, pour la validation) :
      - Réception fournisseur : fournisseur_id + reference (n° de bordereau) ;
      - Retour client : reference (nom/référence du client) + motif
        (texte libre, optionnel) ;
      - Régularisation : motif (obligatoire — une courte catégorie,
        éventuellement suivie d'un détail libre pour « Autre »)."""

    __tablename__ = "entrees"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    # server_default : les entrées déjà en base avant cette fonctionnalité
    # étaient toutes des réceptions fournisseur (la seule sorte qui
    # existait alors) — la migration les classe donc ainsi plutôt que de
    # laisser une valeur vide.
    type_entree = db.Column(db.String(30), nullable=False, server_default="reception_fournisseur")
    fournisseur_id = db.Column(db.Integer, db.ForeignKey("fournisseurs.id"), nullable=True)
    # reference : nom/référence du client (retour_client seulement — une
    # réception fournisseur utilise désormais ses propres colonnes dédiées
    # ci-dessous plutôt que ce champ générique).
    reference = db.Column(db.String(50), nullable=True)
    motif = db.Column(db.String(255), nullable=True)
    # Les champs suivants ne sont renseignés que pour une réception
    # fournisseur (voir add_entree) — decrivent la livraison physique
    # elle-même (véhicule, chauffeur) et SES DEUX documents distincts :
    # le bon de livraison est émis par le fournisseur (accompagne la
    # marchandise), le bordereau de réception est établi en interne à la
    # réception — deux numéros différents, jamais l'un pour l'autre.
    numero_vehicule = db.Column(db.String(50), nullable=True)
    nom_chauffeur = db.Column(db.String(150), nullable=True)
    num_bon_livraison_fournisseur = db.Column(db.String(50), nullable=True)
    num_bordereau_reception = db.Column(db.String(50), nullable=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=True)

    utilisateur = db.relationship("Utilisateur")
    fournisseur = db.relationship("Fournisseur")

    def __repr__(self):
        return f"<Entree article={self.article_id} +{self.quantite}>"

    @property
    def type_entree_libelle(self):
        return TYPES_ENTREE.get(self.type_entree, (self.type_entree, "secondary"))[0]

    @property
    def type_entree_classe(self):
        return TYPES_ENTREE.get(self.type_entree, (self.type_entree, "secondary"))[1]


# Libellé + classe Bootstrap affichés pour chaque type de sortie de stock
# (voir Sortie.type_sortie ci-dessous et apps/gtc_data.py, add_sortie) —
# même principe que TYPES_ENTREE.
TYPES_SORTIE = {
    "mouvement_sortie": ("Mouvement de sortie", "danger"),
    "regularisation": ("Régularisation", "warning"),
}


class Sortie(db.Model):
    """Sortie de stock : mouvement standard (livraison/consommation, avec
    justificatif), ou régularisation de stock (voir TYPES_SORTIE). Champs
    utilisés selon le type (voir apps/gtc_data.py, add_sortie) :
      - Mouvement de sortie : type_document + reference (n° du document) ;
      - Régularisation : motif (obligatoire — mêmes catégories que pour
        une régularisation d'entrée, voir TYPES_ENTREE), réservée aux
        rôles ROLES_REGULARISATION — pas de justificatif classique."""

    __tablename__ = "sorties"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    # server_default : les sorties déjà en base avant cette fonctionnalité
    # étaient toutes des mouvements de sortie standard (la seule sorte qui
    # existait alors) — la migration les classe donc ainsi.
    type_sortie = db.Column(db.String(30), nullable=False, server_default="mouvement_sortie")
    type_document = db.Column(db.String(50), nullable=True)
    reference = db.Column(db.String(50), nullable=True)
    motif = db.Column(db.String(255), nullable=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=True)

    utilisateur = db.relationship("Utilisateur")

    def __repr__(self):
        return f"<Sortie article={self.article_id} -{self.quantite}>"

    @property
    def type_sortie_libelle(self):
        return TYPES_SORTIE.get(self.type_sortie, (self.type_sortie, "secondary"))[0]

    @property
    def type_sortie_classe(self):
        return TYPES_SORTIE.get(self.type_sortie, (self.type_sortie, "secondary"))[1]


class Transfert(db.Model):
    """Transfert de stock d'un magasin vers un autre (voir
    apps/gtc_data.py, transferer_stock). Se traduit TOUJOURS par exactement
    une Sortie (côté magasin_source) et une Entree (côté magasin_destination) —
    reliées ici pour l'historique, et portant chacune la même `reference`
    (ex. "TRF-2026-0007") que ce transfert, pour rester reliables même en
    consultant Entree/Sortie isolément (pages Entrées / Sorties).

    `reference` est le numéro affiché à l'utilisateur (compteur remis à
    zéro chaque année, voir gtc_data._prochaine_reference_transfert)."""

    __tablename__ = "transferts"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    magasin_source_id = db.Column(db.Integer, db.ForeignKey("magasins.id"), nullable=False)
    magasin_destination_id = db.Column(db.Integer, db.ForeignKey("magasins.id"), nullable=False)
    # Article tel qu'il existe dans chaque magasin — deux lignes Article
    # distinctes (même référence/désignation, chacune unique dans son
    # magasin depuis l'Étape 0) ; article_destination a pu être créé par
    # ce transfert lui-même s'il n'existait pas encore là-bas (voir
    # transferer_stock).
    article_source_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    article_destination_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    sortie_id = db.Column(db.Integer, db.ForeignKey("sorties.id"), unique=True, nullable=False)
    entree_id = db.Column(db.Integer, db.ForeignKey("entrees.id"), unique=True, nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=True)

    magasin_source = db.relationship("Magasin", foreign_keys=[magasin_source_id])
    magasin_destination = db.relationship("Magasin", foreign_keys=[magasin_destination_id])
    article_source = db.relationship("Article", foreign_keys=[article_source_id])
    article_destination = db.relationship("Article", foreign_keys=[article_destination_id])
    sortie = db.relationship("Sortie")
    entree = db.relationship("Entree")
    utilisateur = db.relationship("Utilisateur")

    def __repr__(self):
        return f"<Transfert {self.reference} {self.magasin_source_id}->{self.magasin_destination_id}>"


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
    "transfert_stock": ("Transfert inter-magasin", "primary"),
    "archive_article": ("Archivage article", "secondary"),
    "desarchive_article": ("Désarchivage article", "secondary"),
    "suppression_article": ("Suppression définitive article", "danger"),
    "traiter_alerte": ("Alerte traitée", "success"),
    "purge_journal": ("Purge du journal", "danger"),
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


class Alerte(db.Model):
    """Alerte de suivi de stock — écart de rapprochement avec Sage 100
    ou seuil critique atteint (voir /pages/alertes/). Peut être marquée
    comme traitée (bouton « Marquer comme traitée » ; voir
    apps/gtc_data.py, traiter_alerte), ce qui journalise l'action."""

    __tablename__ = "alertes"

    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(255), nullable=False)
    detail = db.Column(db.String(255), nullable=False)
    # Date d'affichage déjà formatée (pas encore de génération
    # automatique horodatée pour ces alertes — voir le docstring de
    # get_alertes dans apps/gtc_data.py).
    date = db.Column(db.String(50), nullable=False)
    # "ecart" (écart de rapprochement) ou "seuil" (seuil critique atteint).
    type = db.Column(db.String(20), nullable=False)
    icone = db.Column(db.String(50), nullable=False)
    traitee = db.Column(db.Boolean, nullable=False, default=False, server_default=sa.false())
    # Magasin concerné, pour le filtrage par périmètre courant (voir
    # apps/gtc_data.py, _scope_magasin) — NULL si pas encore rattaché.
    magasin_id = db.Column(db.Integer, db.ForeignKey("magasins.id"), nullable=True)

    magasin = db.relationship("Magasin", backref="alertes")

    def __repr__(self):
        return f"<Alerte {self.titre!r} traitee={self.traitee}>"
