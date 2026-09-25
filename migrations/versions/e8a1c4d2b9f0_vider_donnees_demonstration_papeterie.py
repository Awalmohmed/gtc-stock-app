"""vider les donnees de demonstration papeterie

Revision ID: e8a1c4d2b9f0
Revises: a1b2c3d4e5f6
Create Date: 2026-09-25 10:00:00.000000

Les premières migrations inséraient des données fictives de papeterie
(Rame de papier A4, Classeur A4, Stylo bille, Cartouche imprimante,
Chaise bureau ; fournisseurs Papeterie Générale SARL et Bureau Plus
Distribution ; alertes associées), sans rapport avec l'activité de GTC
sarl (denrées alimentaires). On les supprime des bases existantes.

Seules ces données sont visées, identifiées par leurs valeurs exactes
(titre d'alerte, couple nom + référence d'article, nom de fournisseur) :
une donnée réelle n'est jamais touchée. Un article de démo impliqué dans
un transfert inter-magasin ou un bordereau de route (donc manipulé pour
de vrai) est conservé.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8a1c4d2b9f0'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


ALERTES_DEMO = (
    "Écart de rapprochement — Classeur A4",
    "Écart de rapprochement — Stylo bille bleu (boîte)",
    "Seuil critique atteint — Rame de papier A4",
    "Seuil critique atteint — Classeur A4",
)

# (nom, référence) des articles de démonstration.
ARTICLES_DEMO = (
    ("Rame de papier A4", "REF-0021"),
    ("Cartouche imprimante", "REF-0045"),
    ("Classeur A4", "REF-0102"),
    ("Chaise bureau (modèle X)", "REF-0230"),
    ("Stylo bille bleu (boîte)", "REF-0011"),
)

FOURNISSEURS_DEMO = ("Papeterie Générale SARL", "Bureau Plus Distribution")


def upgrade():
    conn = op.get_bind()

    conn.execute(sa.text("DELETE FROM alertes WHERE titre IN :t").bindparams(
        sa.bindparam('t', expanding=True)), {"t": list(ALERTES_DEMO)})

    for nom, reference in ARTICLES_DEMO:
        ids = [row.id for row in conn.execute(sa.text(
            "SELECT id FROM articles WHERE nom = :n AND reference = :r"
        ), {"n": nom, "r": reference})]
        for article_id in ids:
            utilise = conn.execute(sa.text(
                "SELECT 1 FROM transferts WHERE article_source_id = :a "
                "OR article_destination_id = :a "
                "UNION SELECT 1 FROM sorties WHERE article_id = :a "
                "AND bordereau_route_id IS NOT NULL"
            ), {"a": article_id}).first()
            if utilise:
                continue
            conn.execute(sa.text("DELETE FROM entrees WHERE article_id = :a"), {"a": article_id})
            conn.execute(sa.text("DELETE FROM sorties WHERE article_id = :a"), {"a": article_id})
            conn.execute(sa.text("DELETE FROM articles WHERE id = :a"), {"a": article_id})

    for nom in FOURNISSEURS_DEMO:
        fournisseur_id = conn.execute(sa.text(
            "SELECT id FROM fournisseurs WHERE nom = :n"
        ), {"n": nom}).scalar()
        if fournisseur_id is None:
            continue
        # Détache les articles/entrées qui y seraient encore reliés.
        conn.execute(sa.text(
            "UPDATE articles SET fournisseur_id = NULL WHERE fournisseur_id = :f"
        ), {"f": fournisseur_id})
        conn.execute(sa.text(
            "UPDATE entrees SET fournisseur_id = NULL WHERE fournisseur_id = :f"
        ), {"f": fournisseur_id})
        conn.execute(sa.text("DELETE FROM fournisseurs WHERE id = :f"), {"f": fournisseur_id})


def downgrade():
    # Données de démonstration supprimées volontairement : rien à restaurer.
    pass
