# -*- encoding: utf-8 -*-
"""Alertes « Seuil critique atteint » de la page Alertes : créées
automatiquement (gtc_data._ajouter_alerte_seuil) aux mêmes moments que
l'e-mail d'alerte (mailer.envoyer_alerte_seuil) — quand une sortie, un
bordereau de route ou un transfert fait BASCULER un article en alerte ;
jamais pour un mouvement qui le laisse au-dessus du seuil, ni à nouveau
tant qu'il y reste."""
from datetime import date

import pytest

from apps import db
from apps.models import Alerte


@pytest.fixture(autouse=True)
def pas_d_email(monkeypatch):
    """Compte les appels à l'e-mail d'alerte sans rien envoyer."""
    from apps import gtc_data
    appels = []
    monkeypatch.setattr(gtc_data.mailer, "envoyer_alerte_seuil", lambda article: appels.append(article.id))
    return appels


def sortie(client, article_id, quantite, reference="BL-0001"):
    return client.post("/pages/sorties/nouvelle", data={
        "type_sortie": "mouvement_sortie", "article_id": str(article_id),
        "quantite": str(quantite), "date": date.today().isoformat(),
        "type_document": "Bon de livraison", "reference": reference,
    }, follow_redirects=True)


def test_sortie_qui_bascule_en_alerte_cree_une_alerte(
    client, login, gestionnaire_a, magasin_a, creer_article, pas_d_email,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, seuil=5, magasin_id=magasin_a)
    login("gest.a")
    sortie(client, article_id, 6)  # 10 -> 4 <= seuil 5

    alertes = Alerte.query.all()
    assert len(alertes) == 1
    alerte = alertes[0]
    assert alerte.type == "seuil"
    assert alerte.titre == "Seuil critique atteint — Riz Sana 25kg"
    assert alerte.detail == "Quantité actuelle : 4 — Seuil d'alerte : 5"
    assert alerte.magasin_id == magasin_a
    assert alerte.traitee is False
    # L'e-mail existant part toujours, une seule fois.
    assert pas_d_email == [article_id]

    page = client.get("/pages/alertes/").get_data(as_text=True)
    assert "Seuil critique atteint — Riz Sana 25kg" in page
    assert "Non traitée" in page


def test_sortie_au_dessus_du_seuil_ne_cree_pas_d_alerte(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, seuil=5, magasin_id=magasin_a)
    login("gest.a")
    sortie(client, article_id, 2)  # 10 -> 8 > seuil 5
    assert Alerte.query.count() == 0


def test_pas_de_nouvelle_alerte_tant_que_l_article_reste_en_alerte(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, seuil=5, magasin_id=magasin_a)
    login("gest.a")
    sortie(client, article_id, 6, reference="BL-0001")  # bascule -> 1 alerte
    sortie(client, article_id, 2, reference="BL-0002")  # reste en alerte
    assert Alerte.query.count() == 1


def test_bordereau_de_route_cree_une_alerte_par_article_qui_bascule(
    client, login, gestionnaire_a, magasin_a, creer_article, pas_d_email,
):
    riz = creer_article("Riz Sana 25kg", "REF-R", 10, seuil=5, magasin_id=magasin_a)
    huile = creer_article("Huile 1 L", "REF-H", 50, seuil=5, magasin_id=magasin_a)
    login("gest.a")
    client.post("/pages/sorties/bordereau-route/nouveau", data={
        "numero_bordereau": "BRT-0001", "date_expedition": date.today().isoformat(),
        "destination": "Douala", "client_destinataire": "Client test",
        "bordereau_numero_vehicule": "LT 123 AB", "bordereau_nom_chauffeur": "Chauffeur",
        "bordereau_article_id[]": [str(riz), str(huile)],
        "bordereau_quantite[]": ["7", "10"],  # riz 10 -> 3 (alerte), huile 50 -> 40 (OK)
        "bordereau_observation[]": ["", ""],
    }, follow_redirects=True)

    assert [a.titre for a in Alerte.query.all()] == ["Seuil critique atteint — Riz Sana 25kg"]
    assert pas_d_email == [riz]


def test_transfert_qui_bascule_la_source_en_alerte_cree_une_alerte(
    client, login, admin, magasin_a, magasin_b, creer_article, pas_d_email,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, 5, magasin_a)
    login("admin.test")
    client.post("/pages/transferts/nouveau", data={
        "magasin_source_id": str(magasin_a), "magasin_destination_id": str(magasin_b),
        "article_id": str(article_id), "quantite": "7",  # source 10 -> 3
        "date": date.today().isoformat(),
    }, follow_redirects=True)

    alertes = Alerte.query.all()
    assert len(alertes) == 1
    # Rattachée au magasin SOURCE (celui dont le stock a baissé).
    assert alertes[0].magasin_id == magasin_a
    assert alertes[0].detail == "Quantité actuelle : 3 — Seuil d'alerte : 5"
    assert pas_d_email == [article_id]
