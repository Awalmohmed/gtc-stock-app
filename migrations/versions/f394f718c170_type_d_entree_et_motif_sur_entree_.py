"""type d'entree et motif sur entree (reception, retour client, regularisation)

Revision ID: f394f718c170
Revises: cfa3d99ca7db
Create Date: 2026-09-14 14:19:54.963656

Ajoute deux colonnes à `entrees` pour distinguer une vraie réception
fournisseur d'un retour client ou d'une régularisation de stock (voir
apps/models.py, Entree/TYPES_ENTREE, et apps/gtc_data.py, add_entree) :
  - type_entree (obligatoire) : classe le mouvement. Les entrées déjà en
    base sont toutes classées "reception_fournisseur" via server_default
    (la seule sorte qui existait avant cette fonctionnalité) — aucune ne
    reste donc non classée.
  - motif (facultatif) : motif du retour (texte libre) ou de la
    régularisation (catégorie courte, éventuellement suivie d'un détail
    libre pour "Autre").
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f394f718c170'
down_revision = 'cfa3d99ca7db'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'entrees',
        sa.Column('type_entree', sa.String(length=30), nullable=False,
                  server_default='reception_fournisseur'),
    )
    op.add_column('entrees', sa.Column('motif', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('entrees', 'motif')
    op.drop_column('entrees', 'type_entree')
