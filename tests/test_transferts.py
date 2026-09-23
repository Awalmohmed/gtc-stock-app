# -*- encoding: utf-8 -*-
"""Transferts inter-magasins (voir gtc_data.transferer_stock) : déplace
du stock d'un magasin vers un autre en une opération atomique."""
from datetime import date

from apps import db
from apps.models import Article, Transfert


def test_transfert_deplace_le_stock_entre_magasins(
    client, login, admin, magasin_a, magasin_b, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)

    login("admin.test")
    resp = client.post(
        "/pages/transferts/nouveau",
        data={
            "magasin_source_id": str(magasin_a),
            "magasin_destination_id": str(magasin_b),
            "article_id": str(article_id),
            "quantite": "4",
            "date": date.today().isoformat(),
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "enregistr" in page

    article_source = db.session.get(Article, article_id)
    assert article_source.quantite == 6

    article_destination = Article.query.filter_by(reference="REF-A", magasin_id=magasin_b).first()
    assert article_destination is not None
    assert article_destination.quantite == 4

    transfert = Transfert.query.first()
    assert transfert is not None
    assert transfert.quantite == 4
    assert transfert.magasin_source_id == magasin_a
    assert transfert.magasin_destination_id == magasin_b


def test_transfert_refuse_si_stock_source_insuffisant(
    client, login, admin, magasin_a, magasin_b, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 5, 2, magasin_a)

    login("admin.test")
    resp = client.post(
        "/pages/transferts/nouveau",
        data={
            "magasin_source_id": str(magasin_a),
            "magasin_destination_id": str(magasin_b),
            "article_id": str(article_id),
            "quantite": "6",  # > 5 disponibles
            "date": date.today().isoformat(),
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "insuffisant" in page.lower()
    assert db.session.get(Article, article_id).quantite == 5  # inchangé
    assert Transfert.query.count() == 0


def test_transfert_refuse_magasin_source_egal_destination(
    client, login, admin, magasin_a, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)

    login("admin.test")
    resp = client.post(
        "/pages/transferts/nouveau",
        data={
            "magasin_source_id": str(magasin_a),
            "magasin_destination_id": str(magasin_a),
            "article_id": str(article_id),
            "quantite": "1",
            "date": date.today().isoformat(),
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "différents" in page.lower() or "diff\xe9rents" in page.lower()
    assert Transfert.query.count() == 0


def test_gestionnaire_ne_peut_transferer_que_depuis_son_propre_magasin(
    client, login, gestionnaire_a, magasin_a, magasin_b, creer_article,
):
    """Un Gestionnaire de stock ne choisit pas librement le magasin
    source (contrairement à un Administrateur) : le sien est imposé
    côté serveur, jamais celui posté dans le formulaire."""
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)

    login("gest.a")
    resp = client.post(
        "/pages/transferts/nouveau",
        data={
            "magasin_source_id": str(magasin_b),  # tentative de forcer un autre magasin
            "magasin_destination_id": str(magasin_a),
            "article_id": str(article_id),
            "quantite": "1",
            "date": date.today().isoformat(),
        },
        follow_redirects=True,
    )
    # Le magasin source réellement utilisé reste magasin_a (le sien) :
    # magasin_b == magasin_a est refusé par transferer_stock (magasins
    # source/destination identiques), la tentative est donc rejetée.
    page = resp.get_data(as_text=True)
    assert "différents" in page.lower() or "diff\xe9rents" in page.lower()
    assert db.session.get(Article, article_id).quantite == 10


def test_transfert_reserve_gestionnaire_et_admin(client, login, comptable, magasin_a, magasin_b):
    """La page de transfert est réservée à un Gestionnaire de stock ou
    un Administrateur (@roles_required) — pas à un Comptable."""
    login("comptable.test")
    resp = client.get("/pages/transferts/", follow_redirects=True)
    page = resp.get_data(as_text=True)
    assert "droits" in page.lower() or "administrateur" in page.lower()
