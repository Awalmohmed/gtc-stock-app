"""num bordereau reception distinct du bon de livraison fournisseur

Revision ID: d42c49e58519
Revises: 044ca107370f
Create Date: 2026-09-14 15:08:28.625572

Une réception fournisseur porte DEUX documents distincts, jamais l'un
pour l'autre : le bon de livraison (émis par le fournisseur, accompagne
la marchandise — num_bon_livraison_fournisseur, ajouté par la migration
précédente) et le bordereau de réception (établi en interne à la
réception — num_bordereau_reception ici, le champ d'origine de cette
fonctionnalité avant l'ajout du bon de livraison).

La migration précédente (044ca107370f) avait déplacé l'ancien numéro de
bordereau — collecté par le tout premier formulaire, avant l'existence
du bon de livraison — dans num_bon_livraison_fournisseur, le seul champ
document qui existait alors. Cette migration corrige cette étiquette :
cette donnée est bien un numéro de BORDEREAU, jamais un bon de livraison
(qui n'a jamais été collecté avant aujourd'hui) — on la déplace donc
vers sa colonne dédiée, et on vide num_bon_livraison_fournisseur pour
ces lignes (aucun vrai numéro de BL n'existe pour elles).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd42c49e58519'
down_revision = '044ca107370f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('entrees', sa.Column('num_bordereau_reception', sa.String(length=50), nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE entrees SET num_bordereau_reception = num_bon_livraison_fournisseur, "
        "num_bon_livraison_fournisseur = NULL "
        "WHERE type_entree = 'reception_fournisseur' AND num_bon_livraison_fournisseur IS NOT NULL"
    ))


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE entrees SET num_bon_livraison_fournisseur = num_bordereau_reception "
        "WHERE type_entree = 'reception_fournisseur' AND num_bordereau_reception IS NOT NULL"
    ))
    op.drop_column('entrees', 'num_bordereau_reception')
