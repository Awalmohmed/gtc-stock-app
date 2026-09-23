# -*- encoding: utf-8 -*-
"""Cloisonnement multi-magasin : un Gestionnaire de stock ne voit et ne
mouvemente que les articles de son propre magasin ; un Administrateur/
Comptable voit tous les magasins (voir apps/gtc_data.py, _scope_magasin
/ _filtrer_articles)."""
from datetime import date


def test_gestionnaire_ne_voit_que_les_articles_de_son_magasin(
    client, login, gestionnaire_a, magasin_a, magasin_b, creer_article,
):
    creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)
    creer_article("Huile 5L", "REF-B", 10, 2, magasin_b)

    login("gest.a")
    resp = client.get("/pages/fiche-stock/")
    page = resp.get_data(as_text=True)
    assert "Riz Sana 25kg" in page
    assert "Huile 5L" not in page


def test_admin_voit_tous_les_magasins(
    client, login, admin, magasin_a, magasin_b, creer_article,
):
    creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)
    creer_article("Huile 5L", "REF-B", 10, 2, magasin_b)

    login("admin.test")
    resp = client.get("/pages/fiche-stock/")
    page = resp.get_data(as_text=True)
    assert "Riz Sana 25kg" in page
    assert "Huile 5L" in page


def test_gestionnaire_ne_peut_pas_mouvementer_un_article_hors_de_son_magasin(
    client, login, gestionnaire_a, magasin_a, magasin_b, creer_article,
):
    """Même en forgeant directement l'article_id d'un article d'un AUTRE
    magasin dans la requête POST, la sortie doit être refusée — la
    protection doit être côté serveur, pas seulement l'UI qui ne montre
    pas l'article (voir gtc_data._article_mouvementable)."""
    article_b = creer_article("Huile 5L", "REF-B", 10, 2, magasin_b)

    login("gest.a")
    resp = client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie",
            "article_id": str(article_b),
            "quantite": "1",
            "date": date.today().isoformat(),
            "type_document": "Bon de livraison",
            "reference": "BL-0001",
        },
        follow_redirects=True,
    )
    page = resp.get_data(as_text=True)
    assert "introuvable" in page.lower()

    from apps.models import Article
    from apps import db
    assert db.session.get(Article, article_b).quantite == 10  # inchangé


def test_recherche_article_scope_au_magasin_du_gestionnaire(
    client, login, gestionnaire_a, magasin_a, magasin_b, creer_article,
):
    """L'autocomplétion d'article (/pages/articles/recherche, utilisée
    par les formulaires Entrée/Sortie/Transfert) ne doit jamais faire
    fuiter un article d'un autre magasin vers un Gestionnaire de stock."""
    creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)
    creer_article("Riz Basmati", "REF-B", 10, 2, magasin_b)

    login("gest.a")
    resp = client.get("/pages/articles/recherche?q=Riz")
    noms = [a["nom"] for a in resp.get_json()]
    assert "Riz Sana 25kg" in noms
    assert "Riz Basmati" not in noms


def test_filtre_magasin_topbar_restreint_un_admin_a_un_seul_magasin(
    client, login, admin, magasin_a, magasin_b, creer_article,
):
    """Le sélecteur de magasin de la barre supérieure (réservé aux rôles
    qui voient tous les magasins) permet à un Administrateur de se
    restreindre temporairement à un seul magasin."""
    creer_article("Riz Sana 25kg", "REF-A", 10, 2, magasin_a)
    creer_article("Huile 5L", "REF-B", 10, 2, magasin_b)

    login("admin.test")
    client.post("/pages/magasin-filtre", data={"magasin_id": str(magasin_a)},
                follow_redirects=True)
    resp = client.get("/pages/fiche-stock/")
    page = resp.get_data(as_text=True)
    assert "Riz Sana 25kg" in page
    assert "Huile 5L" not in page
