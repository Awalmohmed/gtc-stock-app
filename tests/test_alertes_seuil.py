# -*- encoding: utf-8 -*-
"""Génération d'alertes de seuil : une sortie qui fait passer un article
sous (ou à) son seuil d'alerte doit basculer son statut sur "Alerte" et
déclencher UNE notification (mailer.envoyer_alerte_seuil) — jamais à
chaque sortie suivante tant qu'il y reste (voir gtc_data.add_sortie,
"notifie uniquement sur la transition vers l'alerte")."""
from datetime import date

from apps import db
from apps.models import Article


def test_sortie_sous_le_seuil_bascule_le_statut_en_alerte(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, seuil=5, magasin_id=magasin_a)
    assert db.session.get(Article, article_id).statut == "OK"

    login("gest.a")
    client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie",
            "article_id": str(article_id),
            "quantite": "6",  # 10 - 6 = 4 <= seuil (5)
            "date": date.today().isoformat(),
            "type_document": "Bon de livraison",
            "reference": "BL-0001",
        },
        follow_redirects=True,
    )
    article = db.session.get(Article, article_id)
    assert article.quantite == 4
    assert article.statut == "Alerte"


def test_sortie_au_dessus_du_seuil_ne_declenche_pas_l_alerte(
    client, login, gestionnaire_a, magasin_a, creer_article,
):
    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, seuil=5, magasin_id=magasin_a)

    login("gest.a")
    client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie",
            "article_id": str(article_id),
            "quantite": "2",  # 10 - 2 = 8 > seuil (5)
            "date": date.today().isoformat(),
            "type_document": "Bon de livraison",
            "reference": "BL-0002",
        },
        follow_redirects=True,
    )
    assert db.session.get(Article, article_id).statut == "OK"


def test_notification_envoyee_uniquement_sur_la_transition(
    client, login, gestionnaire_a, magasin_a, creer_article, monkeypatch,
):
    """mailer.envoyer_alerte_seuil ne doit être appelée QUE lorsque
    l'article vient de BASCULER en alerte — jamais pour une sortie
    supplémentaire qui l'y laisse simplement."""
    appels = []
    import apps.gtc_data as gtc_data
    monkeypatch.setattr(gtc_data.mailer, "envoyer_alerte_seuil", lambda article: appels.append(article.id))

    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, seuil=5, magasin_id=magasin_a)
    login("gest.a")

    # 1ère sortie : fait basculer l'article en alerte (10 -> 4) -> notifié.
    client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie", "article_id": str(article_id),
            "quantite": "6", "date": date.today().isoformat(),
            "type_document": "Bon de livraison", "reference": "BL-0001",
        },
        follow_redirects=True,
    )
    assert appels == [article_id]

    # 2e sortie : l'article RESTE en alerte (4 -> 2) -> pas de nouvel appel.
    client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie", "article_id": str(article_id),
            "quantite": "2", "date": date.today().isoformat(),
            "type_document": "Bon de livraison", "reference": "BL-0002",
        },
        follow_redirects=True,
    )
    assert appels == [article_id]  # toujours un seul appel


def test_reception_qui_repasse_au_dessus_du_seuil_puis_nouvelle_sortie_renotifie(
    client, login, gestionnaire_a, magasin_a, fournisseur, creer_article, monkeypatch,
):
    """Une fois repassé au-dessus du seuil (par une réception), une
    NOUVELLE sortie qui refait basculer l'article en alerte doit à
    nouveau déclencher une notification (transition redevenue "OK -> Alerte")."""
    appels = []
    import apps.gtc_data as gtc_data
    monkeypatch.setattr(gtc_data.mailer, "envoyer_alerte_seuil", lambda article: appels.append(article.id))

    article_id = creer_article("Riz Sana 25kg", "REF-A", 10, seuil=5, magasin_id=magasin_a, fournisseur_id=fournisseur)
    login("gest.a")

    client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie", "article_id": str(article_id),
            "quantite": "6", "date": date.today().isoformat(),
            "type_document": "Bon de livraison", "reference": "BL-0001",
        },
        follow_redirects=True,
    )
    assert db.session.get(Article, article_id).statut == "Alerte"
    assert len(appels) == 1

    # Réception : repasse au-dessus du seuil (4 -> 20).
    client.post(
        "/pages/entrees/nouvelle",
        data={
            "type_entree": "reception_fournisseur", "article_id": str(article_id),
            "quantite": "16", "date": date.today().isoformat(),
            "numero_vehicule": "AB-123-CD", "nom_chauffeur": "Jean Dupont",
            "num_bon_livraison_fournisseur": "BL-1", "num_bordereau_reception": "BR-1",
        },
        follow_redirects=True,
    )
    assert db.session.get(Article, article_id).statut == "OK"

    # Nouvelle sortie qui refait basculer en alerte -> nouvel appel.
    client.post(
        "/pages/sorties/nouvelle",
        data={
            "type_sortie": "mouvement_sortie", "article_id": str(article_id),
            "quantite": "17", "date": date.today().isoformat(),
            "type_document": "Bon de livraison", "reference": "BL-0003",
        },
        follow_redirects=True,
    )
    assert db.session.get(Article, article_id).statut == "Alerte"
    assert len(appels) == 2
