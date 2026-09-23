# Suite de tests — GTC Stock

Tests automatisés basés sur **pytest** et le client de test Flask.
Chaque test tourne contre une base **SQLite en mémoire**, recréée
intégralement avant chaque test (voir `conftest.py`, fixture `app`) —
la vraie base (`gtc_stock.sqlite3`) n'est jamais touchée, et l'ordre
d'exécution des tests n'a aucune importance.

## Installer les dépendances

Depuis la racine du projet (idéalement dans le même environnement
virtuel que l'application) :

```bash
pip install -r requirements-dev.txt
```

## Lancer les tests

Depuis la racine du projet :

```bash
pytest -v
```

Quelques variantes utiles :

```bash
# Un seul fichier
pytest tests/test_auth.py -v

# Un seul test précis
pytest tests/test_auth.py::test_verrouillage_apres_plusieurs_echecs -v

# S'arrêter au premier échec
pytest -x

# Avec la couverture de code (nécessite pytest-cov : pip install pytest-cov)
pytest --cov=apps
```

## Organisation

| Fichier | Couvre |
|---|---|
| `conftest.py` | Fixtures partagées : `app`/`client` (base fraîche à chaque test), `admin`/`comptable`/`gestionnaire_a`/`gestionnaire_b`, `magasin_a`/`magasin_b`, `login`, `creer_article`. |
| `test_auth.py` | Connexion valide/invalide, compte désactivé, verrouillage après plusieurs échecs (anti brute-force). |
| `test_multi_magasin.py` | Cloisonnement multi-magasin : un Gestionnaire de stock ne voit/mouvemente que son magasin ; un Administrateur/Comptable voit tout. |
| `test_mouvements_stock.py` | Entrées et sorties de stock, y compris le refus d'un stock négatif. |
| `test_transferts.py` | Transferts inter-magasins (déplacement atomique, refus si stock insuffisant ou magasins identiques). |
| `test_alertes_seuil.py` | Passage au statut "Alerte" quand le stock atteint le seuil, et notification déclenchée uniquement sur la transition. |
| `test_droits_admin.py` | Pages/actions réservées à l'Administrateur (magasins, journal, gestion des utilisateurs, suppression définitive...). |
| `test_journal_purge.py` | Export + vidage du journal d'activité (contenu de l'export, état de la table après, protections en cas d'échec). |

## Écrire un nouveau test

Réutilise les fixtures existantes plutôt que de recréer la base à la
main : `client`, `login`, `admin`/`gestionnaire_a`/`comptable`,
`magasin_a`/`magasin_b`, `creer_article`. Exemple minimal :

```python
def test_quelque_chose(client, login, gestionnaire_a, magasin_a, creer_article):
    article_id = creer_article("Riz Sana 25kg", "REF-001", 10, seuil=2, magasin_id=magasin_a)
    login("gest.a")
    resp = client.get("/pages/fiche-stock/")
    assert "Riz Sana 25kg" in resp.get_data(as_text=True)
```

Le mot de passe de tous les comptes de test est `conftest.MOT_DE_PASSE_TEST`
(`"MotDePasse123!"`).
