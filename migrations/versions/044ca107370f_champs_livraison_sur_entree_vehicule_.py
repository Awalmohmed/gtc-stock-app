"""champs livraison sur entree (vehicule, chauffeur, bon de livraison)

Revision ID: 044ca107370f
Revises: f394f718c170
Create Date: 2026-09-14 14:37:53.185105

Ajoute trois colonnes à `entrees`, utilisées seulement pour une réception
fournisseur (voir apps/models.py, Entree, et apps/gtc_data.py, add_entree) :
numero_vehicule, nom_chauffeur, num_bon_livraison_fournisseur — cette
dernière remplace l'usage du champ générique `reference` pour ce type
d'entrée (reference reste, lui, réservé au retour client).

Les réceptions déjà en base ont leur ancien numéro de bordereau dans
`reference` : cette migration le déplace vers la nouvelle colonne dédiée
plutôt que de le perdre, puis vide `reference` pour ces lignes (pour ne
pas dupliquer la même information dans deux colonnes à la fois).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '044ca107370f'
down_revision = 'f394f718c170'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('entrees', sa.Column('numero_vehicule', sa.String(length=50), nullable=True))
    op.add_column('entrees', sa.Column('nom_chauffeur', sa.String(length=150), nullable=True))
    op.add_column('entrees', sa.Column('num_bon_livraison_fournisseur', sa.String(length=50), nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE entrees SET num_bon_livraison_fournisseur = reference, reference = NULL "
        "WHERE type_entree = 'reception_fournisseur' AND reference IS NOT NULL"
    ))


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE entrees SET reference = num_bon_livraison_fournisseur "
        "WHERE type_entree = 'reception_fournisseur' AND num_bon_livraison_fournisseur IS NOT NULL"
    ))
    op.drop_column('entrees', 'num_bon_livraison_fournisseur')
    op.drop_column('entrees', 'nom_chauffeur')
    op.drop_column('entrees', 'numero_vehicule')
