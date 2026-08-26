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
