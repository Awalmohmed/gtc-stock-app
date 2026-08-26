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


class Utilisateur(db.Model):
    """Compte utilisateur de l'application GTC Stock."""

    __tablename__ = "utilisateurs"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False)
    identifiant = db.Column(db.String(80), unique=True, nullable=False, index=True)
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    actif = db.Column(db.Boolean, nullable=False, default=True)
    derniere_connexion = db.Column(db.String(50), nullable=True, default="—")

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
