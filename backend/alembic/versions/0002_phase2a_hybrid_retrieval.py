"""phase2a hybrid retrieval

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. add evidence_units.embedding VECTOR(384) NULL
    op.add_column('evidence_units', sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True))
    
    # 2. add embedding_model nullable string
    op.add_column('evidence_units', sa.Column('embedding_model', sa.String(length=255), nullable=True))
    
    # 3. add embedding_content_hash nullable VARCHAR(64)
    op.add_column('evidence_units', sa.Column('embedding_content_hash', sa.String(length=64), nullable=True))

    # 4. create HNSW cosine index
    op.create_index(
        'ix_evidence_units_embedding', 
        'evidence_units', 
        ['embedding'], 
        unique=False, 
        postgresql_using='hnsw', 
        postgresql_with={'m': 16, 'ef_construction': 64}, 
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )

    # 5. create GIN expression index for lexical search
    op.execute("""
        CREATE INDEX ix_evidence_units_searchable_text_tsvector ON evidence_units USING gin (
            to_tsvector(
                'english',
                coalesce(original_text, '') || ' ' ||
                coalesce(extracted_description, '') || ' ' ||
                coalesce(topic, '') || ' ' ||
                coalesce(subtopic, '')
            )
        )
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_evidence_units_searchable_text_tsvector")
    op.drop_index('ix_evidence_units_embedding', table_name='evidence_units', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_column('evidence_units', 'embedding_content_hash')
    op.drop_column('evidence_units', 'embedding_model')
    op.drop_column('evidence_units', 'embedding')
