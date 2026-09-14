"""creer table transferts inter-magasin

Revision ID: cfa3d99ca7db
Revises: 80cd59792583
Create Date: 2026-09-14 13:11:00.216613

Étape 1 du transfert inter-magasin : nouvelle table `transferts`, une
ligne par transfert effectué, reliant la Sortie (magasin source) et
l'Entree (magasin destination) qu'il a générées — voir apps/models.py,
Transfert, et apps/gtc_data.py, transferer_stock.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cfa3d99ca7db'
down_revision = '80cd59792583'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'transferts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(length=20), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('quantite', sa.Integer(), nullable=False),
        sa.Column('magasin_source_id', sa.Integer(), nullable=False),
        sa.Column('magasin_destination_id', sa.Integer(), nullable=False),
        sa.Column('article_source_id', sa.Integer(), nullable=False),
        sa.Column('article_destination_id', sa.Integer(), nullable=False),
        sa.Column('sortie_id', sa.Integer(), nullable=False),
        sa.Column('entree_id', sa.Integer(), nullable=False),
        sa.Column('utilisateur_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['magasin_source_id'], ['magasins.id']),
        sa.ForeignKeyConstraint(['magasin_destination_id'], ['magasins.id']),
        sa.ForeignKeyConstraint(['article_source_id'], ['articles.id']),
        sa.ForeignKeyConstraint(['article_destination_id'], ['articles.id']),
        sa.ForeignKeyConstraint(['sortie_id'], ['sorties.id']),
        sa.ForeignKeyConstraint(['entree_id'], ['entrees.id']),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateurs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sortie_id'),
        sa.UniqueConstraint('entree_id'),
    )
    with op.batch_alter_table('transferts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_transferts_reference'), ['reference'], unique=True)


def downgrade():
    with op.batch_alter_table('transferts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_transferts_reference'))
    op.drop_table('transferts')
