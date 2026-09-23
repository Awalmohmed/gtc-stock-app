# -*- encoding: utf-8 -*-
"""Authentification : connexion valide/invalide, compte désactivé,
verrouillage après plusieurs échecs (voir apps/rate_limit.py)."""
from apps.rate_limit import MAX_ECHECS
from apps.models import Utilisateur
from apps import db

from conftest import MOT_DE_PASSE_TEST


def test_connexion_valide_redirige_vers_le_dashboard(client, admin, login):
    resp = login("admin.test")
    assert resp.status_code == 200
    # La session porte bien l'identité connectée (utilisée par tout le
    # reste de l'app — current_user(), décorateurs de rôle...).
    with client.session_transaction() as session:
        assert session["identifiant"] == "admin.test"
        assert session["role"] == "Administrateur"


def test_connexion_mot_de_passe_incorrect_refusee(client, admin, login):
    resp = login("admin.test", "mauvais-mot-de-passe")
    assert resp.status_code == 200
    page = resp.get_data(as_text=True)
    assert "incorrect" in page
    with client.session_transaction() as session:
        assert "identifiant" not in session


def test_connexion_identifiant_inconnu_refusee(client, app, login):
    resp = login("personne.nexiste.pas")
    page = resp.get_data(as_text=True)
    assert "incorrect" in page
    with client.session_transaction() as session:
        assert "identifiant" not in session


def test_connexion_compte_desactive_refusee(client, admin, login):
    utilisateur = db.session.get(Utilisateur, admin)
    utilisateur.actif = False
    db.session.commit()

    resp = login("admin.test")
    page = resp.get_data(as_text=True)
    assert "incorrect" in page
    with client.session_transaction() as session:
        assert "identifiant" not in session


def test_verrouillage_apres_plusieurs_echecs(client, admin, login):
    """Après MAX_ECHECS échecs consécutifs sur le même identifiant, même
    le BON mot de passe est refusé jusqu'à expiration du blocage — voir
    apps/rate_limit.py (fenêtre glissante de 15 minutes). Le blocage n'est
    constaté qu'à la tentative SUIVANTE (celle qui déclenche le seuil
    affiche encore "incorrect" : le compteur n'est incrémenté, et le
    blocage posé, qu'après l'échec de CETTE tentative-là)."""
    for _ in range(MAX_ECHECS):
        resp = login("admin.test", "mauvais")
    page = resp.get_data(as_text=True)
    assert "incorrect" in page

    # Le compte est maintenant bloqué : le bon mot de passe est REFUSÉ lui aussi.
    resp = login("admin.test")
    page = resp.get_data(as_text=True)
    assert "Trop de tentatives" in page
    with client.session_transaction() as session:
        assert "identifiant" not in session


def test_pas_de_verrouillage_avant_le_seuil(client, admin, login):
    """MAX_ECHECS - 1 échecs ne bloquent pas encore : la connexion reste
    possible avec le bon mot de passe juste après."""
    for _ in range(MAX_ECHECS - 1):
        login("admin.test", "mauvais")
    resp = login("admin.test")
    with client.session_transaction() as session:
        assert session.get("identifiant") == "admin.test"


def test_deconnexion_vide_la_session(client, admin, login):
    login("admin.test")
    client.get("/accounts/logout/")
    with client.session_transaction() as session:
        assert "identifiant" not in session
