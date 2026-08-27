"""identifiant insensible a la casse (collation NOCASE)

Revision ID: f15b3fc87863
Revises: 165304ad9c99
Create Date: 2026-08-27 12:27:44.645974

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f15b3fc87863'
down_revision = '165304ad9c99'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite ne supporte pas ALTER COLUMN directement : le mode batch
    # d'Alembic recrée la table pour changer la collation de `identifiant`
    # en NOCASE (comparaisons, index unique et tri insensibles à la casse).
    with op.batch_alter_table('utilisateurs', schema=None, recreate='always') as batch_op:
        batch_op.alter_column(
            'identifiant',
            existing_type=sa.String(length=80),
            type_=sa.String(length=80, collation='NOCASE'),
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table('utilisateurs', schema=None, recreate='always') as batch_op:
        batch_op.alter_column(
            'identifiant',
            existing_type=sa.String(length=80, collation='NOCASE'),
            type_=sa.String(length=80),
            existing_nullable=False,
        )
