# -*- encoding: utf-8 -*-
"""
Fixtures partagées par toute la suite de tests (voir tests/README.md
pour comment lancer les tests).

Base de données : SQLite en mémoire (jamais le fichier réel
gtc_stock.sqlite3), recréée intégralement avant CHAQUE test (fixture
`app`, function-scoped) — aucun test ne peut donc être affecté par
l'ordre d'exécution ni laisser de données pour le suivant. Les variables
d'environnement DATABASE_URL / WTF_CSRF_ENABLED doivent être posées
AVANT le tout premier `from apps import ...` (apps/config.py les lit une
seule fois, à l'import) — d'où leur mise en place ici, en tête de
conftest.py, qui est toujours collecté par pytest avant les modules de
test eux-mêmes.
"""
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("WTF_CSRF_ENABLED", "False")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from apps import app as flask_app, db
from apps.models import Utilisateur, Magasin, Article, Fournisseur


MOT_DE_PASSE_TEST = "MotDePasse123!"


@pytest.fixture()
def app():
    """Application Flask + base SQLite en mémoire fraîche pour CE test.
    Le contexte applicatif reste actif pendant toute la durée du test
    (nécessaire pour manipuler `db.session` directement, en dehors d'une
    requête HTTP, dans les fixtures/assertions ci-dessous)."""
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Client de test Flask, lié à la même base que la fixture `app`."""
    return app.test_client()


@pytest.fixture()
def magasin_a(app):
    m = Magasin(nom="Magasin Douala-Port")
    db.session.add(m)
    db.session.commit()
    return m.id


@pytest.fixture()
def magasin_b(app):
    m = Magasin(nom="Magasin Yaoundé")
    db.session.add(m)
    db.session.commit()
    return m.id


@pytest.fixture()
def fournisseur(app):
    f = Fournisseur(nom="Fournisseur ACME", contact="acme@example.com")
    db.session.add(f)
    db.session.commit()
    return f.id


def creer_utilisateur(identifiant, role, magasin_id=None, actif=True):
    u = Utilisateur(nom=identifiant.title(), identifiant=identifiant, role=role,
                     actif=actif, magasin_id=magasin_id)
    u.set_password(MOT_DE_PASSE_TEST)
    db.session.add(u)
    db.session.commit()
    return u.id


@pytest.fixture()
def admin(app):
    """Administrateur — voit tous les magasins."""
    return creer_utilisateur("admin.test", "Administrateur")


@pytest.fixture()
def comptable(app):
    """Comptable — voit tous les magasins, ne peut pas régulariser."""
    return creer_utilisateur("comptable.test", "Comptable")


@pytest.fixture()
def gestionnaire_a(app, magasin_a):
    """Gestionnaire de stock rattaché au Magasin A (magasin_a) — ne doit
    voir/mouvementer QUE les articles de ce magasin."""
    return creer_utilisateur("gest.a", "Gestionnaire de stock", magasin_id=magasin_a)


@pytest.fixture()
def gestionnaire_b(app, magasin_b):
    """Gestionnaire de stock rattaché au Magasin B (magasin_b)."""
    return creer_utilisateur("gest.b", "Gestionnaire de stock", magasin_id=magasin_b)


@pytest.fixture()
def login(client):
    """Fixture-fonction : login(identifiant, mot_de_passe=...) connecte
    `client` (POST classique, comme le formulaire de connexion réel) et
    retourne la réponse suivie. En fixture plutôt qu'en import direct
    entre modules de test, pour rester robuste au mode de collecte de
    pytest quel qu'il soit."""
    def _login(identifiant, mot_de_passe=MOT_DE_PASSE_TEST):
        return client.post(
            "/accounts/sign-in/",
            data={"identifiant": identifiant, "mot_de_passe": mot_de_passe},
            follow_redirects=True,
        )
    return _login


@pytest.fixture()
def creer_article(app):
    """Fixture-fonction : creer_article(nom, reference, quantite, seuil,
    magasin_id, fournisseur_id=None) -> id de l'article créé."""
    def _creer(nom, reference, quantite, seuil, magasin_id, fournisseur_id=None):
        a = Article(nom=nom, reference=reference, quantite=quantite, seuil=seuil,
                    statut="Alerte" if quantite <= seuil else "OK",
                    dernier_mouvement="—", magasin_id=magasin_id, fournisseur_id=fournisseur_id)
        db.session.add(a)
        db.session.commit()
        return a.id
    return _creer
