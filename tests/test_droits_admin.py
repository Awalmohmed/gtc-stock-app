# -*- encoding: utf-8 -*-
"""Protection des pages/actions réservées à l'Administrateur (voir
apps/auth.py, admin_required) : un Gestionnaire de stock ou un Comptable
doit systématiquement être refusé, même en connaissant l'URL exacte —
y compris les routes ajoutées récemment (fournisseur rattaché à
l'article, bordereau de route, analyse des articles ne changent rien à
cette protection, mais on vérifie explicitement que rien ne l'a
affaiblie)."""
import pytest

from apps import db
from apps.models import Utilisateur


# Chaque route protégée par @admin_required (voir apps/views.py) — méthode,
# chemin (avec un id factice 1 où nécessaire), et si elle exige un corps
# minimal pour ne pas échouer AVANT même le contrôle de rôle (on veut
# tester le contrôle de rôle, pas une 400 de validation de formulaire).
ROUTES_ADMIN = [
    ("GET", "/pages/magasins/", {}),
    ("POST", "/pages/magasins/nouveau", {"nom": "Test", "adresse": "", "email_alertes": ""}),
    ("GET", "/pages/journal/", {}),
    ("POST", "/pages/journal/exporter-et-vider.pdf", {}),
    ("POST", "/pages/journal/exporter-et-vider.xlsx", {}),
    ("GET", "/accounts/sign-up/", {}),
]


@pytest.mark.parametrize("methode,chemin,donnees", ROUTES_ADMIN)
def test_route_admin_refusee_pour_un_gestionnaire(
    client, login, gestionnaire_a, methode, chemin, donnees,
):
    login("gest.a")
    if methode == "GET":
        resp = client.get(chemin, follow_redirects=True)
    else:
        resp = client.post(chemin, data=donnees, follow_redirects=True)
    page = resp.get_data(as_text=True)
    assert resp.status_code == 200  # redirigé vers une page normale, jamais un crash
    assert "réservée" in page or "administrateurs" in page.lower()


@pytest.mark.parametrize("methode,chemin,donnees", ROUTES_ADMIN)
def test_route_admin_refusee_pour_un_comptable(
    client, login, comptable, methode, chemin, donnees,
):
    login("comptable.test")
    if methode == "GET":
        resp = client.get(chemin, follow_redirects=True)
    else:
        resp = client.post(chemin, data=donnees, follow_redirects=True)
    page = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "réservée" in page or "administrateurs" in page.lower()


@pytest.mark.parametrize("methode,chemin,donnees", ROUTES_ADMIN)
def test_route_admin_refusee_sans_connexion(client, app, methode, chemin, donnees):
    if methode == "GET":
        resp = client.get(chemin, follow_redirects=True)
    else:
        resp = client.post(chemin, data=donnees, follow_redirects=True)
    page = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "connect" in page.lower()  # "connecter" / "connexion"


def test_route_admin_accessible_a_l_administrateur(client, login, admin):
    login("admin.test")
    resp = client.get("/pages/magasins/")
    assert resp.status_code == 200
    assert "réservée" not in resp.get_data(as_text=True)


def test_suppression_definitive_article_reservee_admin(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    """La suppression DÉFINITIVE d'un article (irréversible, contrairement
    à l'archivage) est réservée à l'Administrateur — un Gestionnaire de
    stock peut archiver mais pas supprimer définitivement."""
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)
    login("gest.a")
    resp = client.post(f"/pages/articles/{article_id}/supprimer", follow_redirects=True)
    page = resp.get_data(as_text=True)
    assert "réservée" in page or "administrateurs" in page.lower()

    from apps.models import Article
    assert db.session.get(Article, article_id) is not None  # toujours là


def test_desarchivage_article_reserve_admin(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)
    from apps.models import Article
    article = db.session.get(Article, article_id)
    article.archive = True
    db.session.commit()

    login("gest.a")
    resp = client.post(f"/pages/articles/{article_id}/desarchiver", follow_redirects=True)
    page = resp.get_data(as_text=True)
    assert "réservée" in page or "administrateurs" in page.lower()
    assert db.session.get(Article, article_id).archive is True  # toujours archivé


def test_gestion_utilisateurs_reservee_admin(client, login, gestionnaire_a, gestionnaire_b):
    """Modifier un autre compte, changer son statut, réinitialiser son
    mot de passe : réservé à l'Administrateur."""
    login("gest.a")
    for chemin, donnees in [
        (f"/pages/utilisateurs/{gestionnaire_b}/modifier", {"nom": "X", "role": "Comptable"}),
        (f"/pages/utilisateurs/{gestionnaire_b}/statut", {"actif": "0"}),
        (f"/pages/utilisateurs/{gestionnaire_b}/mot-de-passe",
         {"mot_de_passe": "Autre12345!", "mot_de_passe_confirmation": "Autre12345!"}),
    ]:
        resp = client.post(chemin, data=donnees, follow_redirects=True)
        page = resp.get_data(as_text=True)
        assert "réservée" in page or "administrateurs" in page.lower(), chemin

    # Le compte de gestionnaire_b n'a pas bougé.
    autre = db.session.get(Utilisateur, gestionnaire_b)
    assert autre.actif is True
    assert autre.role == "Gestionnaire de stock"
