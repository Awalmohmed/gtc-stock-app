# -*- encoding: utf-8 -*-
"""Mouvements d'entrée et de sortie de stock, y compris le refus d'un
stock négatif (voir gtc_data.add_sortie : "le stock ne peut jamais
devenir négatif")."""
from datetime import date

from apps import db
from apps.models import Article


def test_entree_reception_fournisseur_augmente_le_stock(
    client, login, gestionnaire_a, magasin_a, fournisseur, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a, fournisseur)

    login("gest.a")
    resp = client.post(
        "/pages/entrees/nouvelle",
        data={
            "type_entree": "reception_fournisseur",
            "article_id": str(article_id),
            "quantite": "20",
            "date": date.today().isoformat(),
            "numero_vehicule": "AB-123-CD",
            "nom_chauffeur": "Jean Dupont",
            "num_bon_livraison_fournisseur": "BL-0001",
            "num_bordereau_reception": "BR-0001",
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "enregistr" in page
    assert db.session.get(Article, article_id).quantite == 30


def test_entree_reception_bloquee_si_article_sans_fournisseur(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    """Un article créé sans fournisseur rattaché (cas hérité, voir
    gtc_data.add_entree) ne peut pas être réceptionné tant que sa fiche
    n'est pas complétée."""
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a, fournisseur_id=None)

    login("gest.a")
    resp = client.post(
        "/pages/entrees/nouvelle",
        data={
            "type_entree": "reception_fournisseur",
            "article_id": str(article_id),
            "quantite": "5",
            "date": date.today().isoformat(),
            "numero_vehicule": "AB-123-CD",
            "nom_chauffeur": "Jean Dupont",
            "num_bon_livraison_fournisseur": "BL-0001",
            "num_bordereau_reception": "BR-0001",
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "fournisseur" in page.lower()
    assert db.session.get(Article, article_id).quantite == 10  # inchangé


def test_sortie_mouvement_diminue_le_stock(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)

    login("gest.a")
    resp = client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie",
            "article_id": str(article_id),
            "quantite": "4",
            "date": date.today().isoformat(),
            "type_document": "Bon de livraison",
            "reference": "BL-0002",
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "enregistr" in page
    assert db.session.get(Article, article_id).quantite == 6


def test_sortie_refusee_si_stock_insuffisant(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    """Le stock ne doit JAMAIS devenir négatif : une sortie dont la
    quantité dépasse le stock disponible est refusée, la quantité en
    base reste inchangée."""
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)

    login("gest.a")
    resp = client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie",
            "article_id": str(article_id),
            "quantite": "11",  # > 10 disponibles
            "date": date.today().isoformat(),
            "type_document": "Bon de livraison",
            "reference": "BL-0003",
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "insuffisant" in page.lower()
    article = db.session.get(Article, article_id)
    assert article.quantite == 10  # inchangé, jamais négatif
    assert article.quantite >= 0


def test_sortie_stock_exactement_epuise_est_autorisee(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    """Vider EXACTEMENT le stock disponible (quantité == stock) reste
    valide — seul un DÉPASSEMENT est refusé."""
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)

    login("gest.a")
    resp = client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie",
            "article_id": str(article_id),
            "quantite": "10",
            "date": date.today().isoformat(),
            "type_document": "Bon de livraison",
            "reference": "BL-0004",
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "enregistr" in page
    assert db.session.get(Article, article_id).quantite == 0


def test_regularisation_sortie_reservee_gestionnaire_et_admin(
    client, login, comptable, magasin_a, creer_article,
):
    """Un Comptable peut saisir un mouvement de sortie standard mais pas
    une régularisation (voir apps.models.ROLES_REGULARISATION)."""
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)

    login("comptable.test")
    resp = client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "regularisation",
            "article_id": str(article_id),
            "quantite": "2",
            "date": date.today().isoformat(),
            "motif_regularisation": "Inventaire",
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "administrateur" in page.lower() or "gestionnaire" in page.lower()
    assert db.session.get(Article, article_id).quantite == 10  # inchangé
