"""type de sortie et motif sur sortie (mouvement, regularisation)

Revision ID: d6bdbf68e1dd
Revises: d42c49e58519
Create Date: 2026-09-16 15:00:35.537267

Ajoute deux colonnes à `sorties`, sur le même principe que la
fonctionnalité équivalente côté entrées (voir apps/models.py,
Sortie/TYPES_SORTIE, et apps/gtc_data.py, add_sortie) :
  - type_sortie (obligatoire) : classe le mouvement. Les sorties déjà en
    base sont toutes classées "mouvement_sortie" via server_default (la
    seule sorte qui existait avant cette fonctionnalité).
  - motif (facultatif) : motif de la régularisation (catégorie courte,
    éventuellement suivie d'un détail libre pour "Autre").
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6bdbf68e1dd'
down_revision = 'd42c49e58519'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'sorties',
        sa.Column('type_sortie', sa.String(length=30), nullable=False,
                  server_default='mouvement_sortie'),
    )
    op.add_column('sorties', sa.Column('motif', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('sorties', 'motif')
    op.drop_column('sorties', 'type_sortie')
