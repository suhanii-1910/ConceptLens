import hashlib
from typing import Optional

def build_canonical_searchable_text(
    original_text: Optional[str],
    extracted_description: Optional[str],
    topic: Optional[str],
    subtopic: Optional[str]
) -> Optional[str]:
    """
    Builds canonical searchable text from evidence unit fields.
    Returns None if all passed fields are empty.

    Fields are ordered:
    1. original_text
    2. extracted_description
    3. topic
    4. subtopic
    """
    parts = []

    # Strictly enforced order
    if original_text:
        parts.append(original_text)
    if extracted_description:
        parts.append(extracted_description)
    if topic:
        parts.append(topic)
    if subtopic:
        parts.append(subtopic)

    # Deduplicate and normalize whitespace
    deduplicated = dict.fromkeys(" ".join(p.split()) for p in parts if p and p.strip())
    canonical_text = "\n\n".join(deduplicated)

    if not canonical_text.strip():
        return None

    return canonical_text

def get_searchable_text_hash(text: str) -> str:
    """Returns a deterministic SHA-256 hash of canonical text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def get_postgresql_fts_expression(model) -> object:
    """
    Returns the SQLAlchemy / PostgresQL expression for searchable text.
    Must match the Python canonical field order exactly for consistency.
    """
    from sqlalchemy import func
    return (
        func.coalesce(model.original_text, '') + ' ' +
        func.coalesce(model.extracted_description, '') + ' ' +
        func.coalesce(model.topic, '') + ' ' +
        func.coalesce(model.subtopic, '')
    )
