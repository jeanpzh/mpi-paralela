from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class QuestionType(str, Enum):
    """Question types available in the system."""
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"


class ExamStatus(str, Enum):
    """Exam status options."""
    DRAFT = "draft"
    ACTIVE = "active"  # Ready for enrollment
    IN_PROGRESS = "in_progress"  # Sessions started, exam is live
    COMPLETED = "completed"  # Exam time finished, ready for evaluation
    ARCHIVED = "archived"


class EvaluationStatus(str, Enum):
    """Evaluation status options."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# Base Models
class QuestionBase(BaseModel):
    """Base question model."""
    content: str = Field(..., description="Question content")
    question_type: QuestionType = Field(..., description="Type of question")
    options: Optional[List[str]] = Field(None, description="Multiple choice options")
    correct_answer: str = Field(..., description="Correct answer")
    points: int = Field(default=1, ge=1, description="Points for correct answer")


class Question(QuestionBase):
    """Question model with ID."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExamBase(BaseModel):
    """Base exam model."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    duration_minutes: int = Field(..., ge=1, description="Exam duration in minutes")
    total_questions: int = Field(default=0, ge=0)
    total_points: int = Field(default=0, ge=0)

    class Config:
        from_attributes = True


class Exam(ExamBase):
    """Complete exam model."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: ExamStatus = Field(default=ExamStatus.DRAFT)
    questions: List[Question] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApplicantBase(BaseModel):
    """Base applicant model."""
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., description="Applicant email address")
    registration_number: Optional[str] = Field(None, max_length=50)


class Applicant(ApplicantBase):
    """Complete applicant model."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ExamEnrollment(BaseModel):
    """Represents the enrollment of an applicant in an exam."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    exam_id: uuid.UUID
    applicant_id: uuid.UUID
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ExamSessionBase(BaseModel):
    """Base exam session model."""
    exam_id: uuid.UUID
    applicant_id: uuid.UUID
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = Field(default="pending")


class ExamSession(ExamSessionBase):
    """Complete exam session model."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ResponseBase(BaseModel):
    """Base response model."""
    session_id: uuid.UUID
    question_id: uuid.UUID
    answer: str = Field(..., description="Applicant's answer")
    is_correct: Optional[bool] = None
    points_earned: Optional[int] = None


class ApplicantResponse(ResponseBase):
    """Complete applicant response model."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class EvaluationResultBase(BaseModel):
    """Base evaluation result model."""
    session_id: uuid.UUID
    total_questions: int = Field(..., ge=0)
    correct_answers: int = Field(..., ge=0)
    total_points: int = Field(..., ge=0)
    score_percentage: float = Field(..., ge=0, le=100)


class EvaluationResult(EvaluationResultBase):
    """Complete evaluation result model."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: EvaluationStatus = Field(default=EvaluationStatus.PENDING)
    evaluation_time: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ResultsReport(BaseModel):
    """Results report model."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    exam_id: uuid.UUID
    total_participants: int = Field(..., ge=0)
    average_score: float = Field(..., ge=0, le=100)
    highest_score: float = Field(..., ge=0, le=100)
    lowest_score: float = Field(..., ge=0, le=100)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


# MPI Coordinator Models
class MPIJobConfig(BaseModel):
    """MPI job configuration."""
    num_processes: int = Field(default=4, ge=1, le=16)
    input_file: str = Field(..., description="Path to input data file")
    output_file: str = Field(..., description="Path to output results file")
    timeout_seconds: int = Field(default=300, ge=1)


class MPIJobResult(BaseModel):
    """MPI job execution result."""
    job_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    config: MPIJobConfig
    status: str = Field(..., description="Job execution status")
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time_seconds: Optional[float] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


# API Request/Response Models
class CreateExamRequest(BaseModel):
    """Request to create a new exam."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    duration_minutes: int = Field(..., ge=1)
    questions: List[QuestionBase] = Field(..., min_length=1)


class StartExamRequest(BaseModel):
    """Request to start an exam session."""
    exam_id: uuid.UUID
    applicant_id: uuid.UUID


class SubmitResponseRequest(BaseModel):
    """Request to submit a response."""
    session_id: uuid.UUID
    question_id: uuid.UUID
    answer: str


class ResponseSubmission(BaseModel):
    """Simple response submission without session_id (already in URL path)."""
    question_id: uuid.UUID
    answer: str = Field(..., description="Applicant's answer")


class EvaluateExamRequest(BaseModel):
    """Request to evaluate exam responses."""
    exam_id: uuid.UUID
    parallel_processes: int = Field(default=4, ge=1, le=16)


class BulkEnrollRequest(BaseModel):
    """Request to enroll multiple applicants in an exam."""
    applicant_ids: List[uuid.UUID] = Field(..., min_length=1)


class ExamStatsResponse(BaseModel):
    """Response with exam statistics."""
    exam_id: uuid.UUID
    total_participants: int
    completed_sessions: int
    average_score: float
    score_distribution: Dict[str, int] 