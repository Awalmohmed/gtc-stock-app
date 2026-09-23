"""creer table bordereaux_route + colonnes associees sur sorties

Revision ID: a1b2c3d4e5f6
Revises: b7f3a9c1d5e6
Create Date: 2026-09-22 10:00:00.000000

Bordereau de route : le document papier réellement utilisé chez GTC sarl
pour justifier une sortie de stock par livraison/expédition, pouvant
couvrir PLUSIEURS articles sous un même numéro (voir apps/models.py,
BordereauRoute, et apps/gtc_data.py, add_bordereau_route). Chaque article
devient sa propre ligne `sorties`, reliée à l'en-tête via
bordereau_route_id ; `observation` est propre à chaque ligne.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'b7f3a9c1d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'bordereaux_route',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.String(length=50), nullable=False),
        sa.Column('date_expedition', sa.Date(), nullable=False),
        sa.Column('magasin_expedition_id', sa.Integer(), nullable=False),
        sa.Column('destination', sa.String(length=150), nullable=False),
        sa.Column('client_destinataire', sa.String(length=150), nullable=False),
        sa.Column('numero_vehicule', sa.String(length=50), nullable=False),
        sa.Column('nom_chauffeur', sa.String(length=150), nullable=False),
        sa.Column('numero_facture', sa.String(length=50), nullable=True),
        sa.Column('utilisateur_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['magasin_expedition_id'], ['magasins.id']),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateurs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('bordereaux_route', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_bordereaux_route_numero'), ['numero'], unique=True)

    with op.batch_alter_table('sorties', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bordereau_route_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('observation', sa.String(length=255), nullable=True))
        batch_op.create_foreign_key(
            'fk_sorties_bordereau_route_id', 'bordereaux_route', ['bordereau_route_id'], ['id'],
        )


def downgrade():
    with op.batch_alter_table('sorties', schema=None) as batch_op:
        batch_op.drop_constraint('fk_sorties_bordereau_route_id', type_='foreignkey')
        batch_op.drop_column('observation')
        batch_op.drop_column('bordereau_route_id')

    with op.batch_alter_table('bordereaux_route', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bordereaux_route_numero'))
    op.drop_table('bordereaux_route')
