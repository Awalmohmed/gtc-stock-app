"""vider les alertes de demonstration

Revision ID: e8a1c4d2b9f0
Revises: a1b2c3d4e5f6
Create Date: 2026-09-25 10:00:00.000000

Les 4 alertes insérées par la migration fb73d9c76e4a (Classeur A4, Stylo
bille bleu, Rame de papier A4) étaient des données fictives de papeterie,
sans rapport avec l'activité de GTC sarl (denrées alimentaires). On les
supprime des bases existantes — et uniquement elles, identifiées par leur
titre exact, pour ne jamais toucher une alerte réelle.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8a1c4d2b9f0'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


TITRES_DEMO = (
    "Écart de rapprochement — Classeur A4",
    "Écart de rapprochement — Stylo bille bleu (boîte)",
    "Seuil critique atteint — Rame de papier A4",
    "Seuil critique atteint — Classeur A4",
)


def upgrade():
    alertes = sa.table('alertes', sa.column('titre', sa.String))
    op.execute(alertes.delete().where(alertes.c.titre.in_(TITRES_DEMO)))


def downgrade():
    # Données de démonstration supprimées volontairement : rien à restaurer.
    pass
