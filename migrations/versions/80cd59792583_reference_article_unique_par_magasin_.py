"""reference article unique par magasin (composee)

Revision ID: 80cd59792583
Revises: fb73d9c76e4a
Create Date: 2026-09-14 00:17:39.166516

La référence d'un article n'est désormais unique que PAR MAGASIN (couple
référence + magasin_id) et non plus sur toute l'application : un même
article (même référence, même désignation) peut exister dans plusieurs
magasins, chacun avec sa propre quantité — notamment suite à un transfert
inter-magasin (voir gtc_data.transferer_stock).

L'ancien index unique ix_articles_reference est remplacé par : un index
simple (non unique) sur reference seule, conservé pour les recherches par
référence sans le magasin (import de fichier, rapprochement Sage 100) ;
et une nouvelle contrainte d'unicité composée sur (reference, magasin_id).

Aucune perte de données : SQLite ne supporte pas ALTER CONSTRAINT
directement, le mode batch d'Alembic recrée donc la table. Avant de le
faire, on vérifie qu'aucune paire (reference, magasin_id) n'est déjà
dupliquée dans les données existantes — ce qui romprait silencieusement
la nouvelle contrainte au moment de la recréation de la table ; si c'est
le cas, la migration s'arrête explicitement plutôt que d'échouer avec une
erreur SQL obscure (ou pire, de perdre des lignes).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '80cd59792583'
down_revision = 'fb73d9c76e4a'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    doublons = conn.execute(sa.text(
        "SELECT reference, magasin_id, COUNT(*) AS n FROM articles "
        "WHERE magasin_id IS NOT NULL "
        "GROUP BY reference, magasin_id HAVING COUNT(*) > 1"
    )).fetchall()
    if doublons:
        raise RuntimeError(
            "Migration interrompue : des articles partagent déjà la même "
            "référence dans le même magasin (" +
            ", ".join(f"{r.reference} / magasin {r.magasin_id}" for r in doublons) +
            "). Corrigez ces doublons avant de relancer la migration."
        )

    with op.batch_alter_table('articles', schema=None, recreate='always') as batch_op:
        batch_op.drop_index(batch_op.f('ix_articles_reference'))
        batch_op.create_index(batch_op.f('ix_articles_reference'), ['reference'], unique=False)
        batch_op.create_unique_constraint('uq_articles_reference_magasin', ['reference', 'magasin_id'])


def downgrade():
    # Retour à l'unicité globale : impossible si des doublons de référence
    # entre magasins ont été créés entre-temps (ex. via un transfert
    # inter-magasin) — la recréation de la table échouera alors
    # explicitement plutôt que de supprimer silencieusement des articles.
    with op.batch_alter_table('articles', schema=None, recreate='always') as batch_op:
        batch_op.drop_constraint('uq_articles_reference_magasin', type_='unique')
        batch_op.drop_index(batch_op.f('ix_articles_reference'))
        batch_op.create_index(batch_op.f('ix_articles_reference'), ['reference'], unique=True)
