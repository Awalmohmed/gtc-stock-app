# -*- encoding: utf-8 -*-
"""Top 3 des ventes du tableau de bord (gtc_data.get_stats, carte « Top 3
des ventes » de dashboard.html) : les 3 articles les plus sortis sur les
30 derniers jours, du plus vendu au moins vendu. Avec moins de 3 articles
vendus sur la période, seuls ceux qui existent sont affichés — et un
message (pas d'erreur) quand il n'y en a aucun."""
import re
from datetime import date, timedelta

import pytest

from apps import db
from apps.models import Sortie


def vendre(article_id, quantite, il_y_a_jours=1):
    db.session.add(Sortie(article_id=article_id, quantite=quantite,
                          date=date.today() - timedelta(days=il_y_a_jours)))
    db.session.commit()


def top_affiche(html):
    """Noms des articles de la carte Top 3, dans l'ordre d'affichage."""
    return [nom.strip() for nom in re.findall(
        r'<div class="top-ventes-row.*?text-dark small fw-semibold"[^>]*>\s*(.*?)\s*</a>',
        html, flags=re.S,
    )]


@pytest.fixture()
def tableau_de_bord(client, login, gestionnaire_a):
    """Fonction : charge le tableau de bord (gestionnaire du magasin A)
    et retourne son HTML, en vérifiant qu'il s'affiche sans erreur."""
    login("gest.a")

    def _charger():
        resp = client.get("/pages/dashboard/")
        assert resp.status_code == 200
        return resp.get_data(as_text=True)
    return _charger


def test_aucune_vente_affiche_un_message(tableau_de_bord, magasin_a, creer_article):
    creer_article("Riz 25 kg", "REF-A", 10, seuil=2, magasin_id=magasin_a)
    html = tableau_de_bord()
    assert top_affiche(html) == []
    assert "Aucune sortie enregistrée sur les 30 derniers jours." in html


@pytest.mark.parametrize("nb_vendus", [1, 2])
def test_moins_de_3_articles_vendus_affiche_seulement_ceux_qui_existent(
    tableau_de_bord, magasin_a, creer_article, nb_vendus,
):
    noms = ["Riz 25 kg", "Huile 1 L", "Sucre 1 kg"]
    ids = [creer_article(n, f"REF-{i}", 100, seuil=2, magasin_id=magasin_a)
           for i, n in enumerate(noms)]
    # Seuls les `nb_vendus` premiers articles ont une sortie ; le dernier
    # (jamais vendu) ne doit pas apparaître, même s'il reste de la place.
    for i in range(nb_vendus):
        vendre(ids[i], quantite=10 * (i + 1))

    html = tableau_de_bord()
    attendu = list(reversed(noms[:nb_vendus]))  # plus grosse quantité en tête
    assert top_affiche(html) == attendu
    assert "Aucune sortie enregistrée" not in html


def test_plus_de_3_articles_vendus_garde_les_3_premiers_dans_l_ordre(
    tableau_de_bord, magasin_a, creer_article,
):
    quantites = {"Riz 25 kg": 5, "Huile 1 L": 40, "Sucre 1 kg": 12, "Lait 400 g": 25}
    for i, (nom, qte) in enumerate(quantites.items()):
        article_id = creer_article(nom, f"REF-{i}", 100, seuil=2, magasin_id=magasin_a)
        vendre(article_id, quantite=qte)

    assert top_affiche(tableau_de_bord()) == ["Huile 1 L", "Lait 400 g", "Sucre 1 kg"]


def test_quantites_cumulees_et_ventes_hors_periode_ignorees(
    tableau_de_bord, magasin_a, creer_article,
):
    riz = creer_article("Riz 25 kg", "REF-R", 100, seuil=2, magasin_id=magasin_a)
    huile = creer_article("Huile 1 L", "REF-H", 100, seuil=2, magasin_id=magasin_a)
    # Riz : 3 sorties de 10 dans la période -> 30 au total.
    for _ in range(3):
        vendre(riz, quantite=10)
    # Huile : 25 dans la période, plus une grosse vente il y a 45 jours,
    # hors des 30 derniers jours, qui ne doit pas compter.
    vendre(huile, quantite=25)
    vendre(huile, quantite=500, il_y_a_jours=45)

    assert top_affiche(tableau_de_bord()) == ["Riz 25 kg", "Huile 1 L"]


def test_ventes_d_un_autre_magasin_ignorees(
    tableau_de_bord, magasin_a, magasin_b, creer_article,
):
    riz_a = creer_article("Riz 25 kg", "REF-A", 100, seuil=2, magasin_id=magasin_a)
    huile_b = creer_article("Huile 1 L", "REF-B", 100, seuil=2, magasin_id=magasin_b)
    vendre(riz_a, quantite=5)
    vendre(huile_b, quantite=50)

    assert top_affiche(tableau_de_bord()) == ["Riz 25 kg"]
