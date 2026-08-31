"""relier entrees a fournisseur_id au lieu du champ texte libre

Revision ID: 7d2038394086
Revises: 0340cf32b856
Create Date: 2026-08-31 15:22:00.138983

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d2038394086'
down_revision = '0340cf32b856'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Ajoute la nouvelle colonne (sans casser les données existantes).
    with op.batch_alter_table('entrees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fournisseur_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_entrees_fournisseur_id', 'fournisseurs', ['fournisseur_id'], ['id'])

    # 2) Fait correspondre chaque ancien nom de fournisseur (texte libre)
    # au fournisseur du même nom déjà en base (voir la migration
    # 0340cf32b856_*.py, qui les a créés).
    op.execute("""
        UPDATE entrees
        SET fournisseur_id = (
            SELECT id FROM fournisseurs WHERE fournisseurs.nom = entrees.fournisseur
        )
        WHERE fournisseur IS NOT NULL
    """)

    # 3) Supprime l'ancien champ texte, devenu inutile.
    with op.batch_alter_table('entrees', schema=None) as batch_op:
        batch_op.drop_column('fournisseur')


def downgrade():
    with op.batch_alter_table('entrees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fournisseur', sa.VARCHAR(length=150), nullable=True))

    op.execute("""
        UPDATE entrees
        SET fournisseur = (
            SELECT nom FROM fournisseurs WHERE fournisseurs.id = entrees.fournisseur_id
        )
        WHERE fournisseur_id IS NOT NULL
    """)

    with op.batch_alter_table('entrees', schema=None) as batch_op:
        batch_op.drop_constraint('fk_entrees_fournisseur_id', type_='foreignkey')
        batch_op.drop_column('fournisseur_id')
