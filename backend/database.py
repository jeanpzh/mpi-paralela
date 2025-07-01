import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from supabase import create_client, Client
import uuid
from datetime import datetime

from config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# SQLAlchemy Models (for local database operations)
class QuestionTable(Base):
    __tablename__ = "questions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    question_type = Column(String(50), nullable=False)
    options = Column(JSONB, nullable=True)
    correct_answer = Column(Text, nullable=False)
    points = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)


class ExamTable(Base):
    """Exams table definition."""
    __tablename__ = "exams"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    description = Column(String(1000))
    duration_minutes = Column(Integer, nullable=False)
    total_questions = Column(Integer, default=0)
    total_points = Column(Integer, default=0)
    status = Column(String(50), default="draft", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    questions = relationship("ExamQuestionTable", back_populates="exam")
    sessions = relationship("ExamSessionTable", back_populates="exam")
    enrollments = relationship("ExamEnrollmentTable", back_populates="exam", cascade="all, delete-orphan")


class ExamQuestionTable(Base):
    """Association table between exams and questions."""
    __tablename__ = "exam_questions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    order_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    exam = relationship("ExamTable", back_populates="questions")


class ApplicantTable(Base):
    """Applicants table definition."""
    __tablename__ = "applicants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    registration_number = Column(String(50), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sessions = relationship("ExamSessionTable", back_populates="applicant")
    enrollments = relationship("ExamEnrollmentTable", back_populates="applicant", cascade="all, delete-orphan")


class ExamEnrollmentTable(Base):
    """Table to store exam enrollments."""
    __tablename__ = "exam_enrollments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    applicant_id = Column(UUID(as_uuid=True), ForeignKey("applicants.id"), nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (UniqueConstraint('exam_id', 'applicant_id', name='_exam_applicant_uc'),)
    
    exam = relationship("ExamTable", back_populates="enrollments")
    applicant = relationship("ApplicantTable", back_populates="enrollments")


class ExamSessionTable(Base):
    """Exam sessions table definition."""
    __tablename__ = "exam_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    applicant_id = Column(UUID(as_uuid=True), ForeignKey("applicants.id"), nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    exam = relationship("ExamTable", back_populates="sessions")
    applicant = relationship("ApplicantTable", back_populates="sessions")


class ResponseTable(Base):
    __tablename__ = "responses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("exam_sessions.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=True)
    points_earned = Column(Integer, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)


class EvaluationTable(Base):
    __tablename__ = "evaluations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("exam_sessions.id"), nullable=False)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    total_points = Column(Integer, nullable=False)
    score_percentage = Column(Float, nullable=False)
    status = Column(String(50), default="pending")
    evaluation_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ResultsReportTable(Base):
    __tablename__ = "results_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    total_participants = Column(Integer, nullable=False)
    average_score = Column(Float, nullable=False)
    highest_score = Column(Float, nullable=False)
    lowest_score = Column(Float, nullable=False)
    statistics = Column(JSONB, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)


# Database setup
def create_engine():
    """Create async database engine."""
    if not settings.database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    
    # Convert postgresql:// to postgresql+asyncpg://
    database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    return create_async_engine(
        database_url,
        echo=settings.debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=300,
    )


# Global engine instance
engine = create_engine()

# Session factory
async_session_maker = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_supabase_client() -> Client:
    """Get Supabase client instance."""
    if not settings.supabase_url or not settings.supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required")
    
    return create_client(settings.supabase_url, settings.supabase_key)


# Initialize database tables
async def create_tables():
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """Drop all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Database initialization
async def init_database():
    """Initialize database with tables."""
    try:
        await create_tables()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating database tables: {e}")
        raise


# Cleanup
async def close_database():
    """Close database connections."""
    await engine.dispose() 