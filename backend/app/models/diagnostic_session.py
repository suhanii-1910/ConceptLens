"""Frozen cold-start question selection; progress is derived from immutable attempts."""
import uuid
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base

class DiagnosticSession(Base):
    __tablename__='diagnostic_sessions'
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    course_id:Mapped[uuid.UUID]=mapped_column(sa.ForeignKey('courses.id',ondelete='CASCADE'))
    learner_id:Mapped[uuid.UUID]
    question_ids:Mapped[list]=mapped_column(JSONB)
    created_at:Mapped[datetime]=mapped_column(sa.DateTime(timezone=True),server_default=sa.func.now())
    __table_args__=(sa.UniqueConstraint('course_id','learner_id',name='uq_diagnostic_learner_course'),)
