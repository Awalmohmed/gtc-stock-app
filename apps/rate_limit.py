# -*- encoding: utf-8 -*-
"""
GTC Stock — Limitation des tentatives de connexion (anti brute-force).

Après MAX_ECHECS échecs consécutifs sur une même clé (identifiant visé
ou adresse IP) dans la fenêtre glissante FENETRE_BLOCAGE, les tentatives
suivantes sur cette clé sont bloquées jusqu'à expiration du blocage.
"""

from datetime import datetime, timedelta

from apps import db
from apps.models import TentativeConnexion

MAX_ECHECS = 5
FENETRE_BLOCAGE = timedelta(minutes=15)


def secondes_avant_deblocage(cle):
    """Retourne le nombre de secondes avant déblocage de `cle`, ou 0 si
    elle n'est pas (ou plus) bloquée."""
    tentative = TentativeConnexion.query.filter_by(cle=cle).first()
    if not tentative or not tentative.bloque_jusqua:
        return 0
    restant = (tentative.bloque_jusqua - datetime.utcnow()).total_seconds()
    return max(0, int(restant))


def enregistrer_echec(cle):
    """Incrémente le compteur d'échecs pour `cle` ; bloque la clé si le
    seuil MAX_ECHECS est atteint."""
    tentative = TentativeConnexion.query.filter_by(cle=cle).first()
    if not tentative:
        tentative = TentativeConnexion(cle=cle, echecs=0)
        db.session.add(tentative)

    maintenant = datetime.utcnow()
    # Un blocage précédent déjà expiré : on repart d'un compteur propre
    # plutôt que de garder un vieil historique d'échecs.
    if tentative.bloque_jusqua and tentative.bloque_jusqua <= maintenant:
        tentative.echecs = 0
        tentative.bloque_jusqua = None

    tentative.echecs += 1
    tentative.derniere_tentative = maintenant
    if tentative.echecs >= MAX_ECHECS:
        tentative.bloque_jusqua = maintenant + FENETRE_BLOCAGE

    db.session.commit()


def reinitialiser(cle):
    """Efface le compteur d'échecs pour `cle` (connexion réussie)."""
    tentative = TentativeConnexion.query.filter_by(cle=cle).first()
    if tentative:
        db.session.delete(tentative)
        db.session.commit()
