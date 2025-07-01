from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid

from models import (
    Exam, Question, Applicant, ExamSession, ApplicantResponse,
    EvaluationResult, ResultsReport, CreateExamRequest,
    StartExamRequest, SubmitResponseRequest, EvaluateExamRequest,
    ExamStatsResponse, MPIJobResult, ApplicantBase, ResponseSubmission,
    BulkEnrollRequest, ExamEnrollment
)
from database import get_db_session, init_database, close_database
from services import (
    ExamManager, ApplicantManager, ExamSessionManager, 
    Evaluator, ReportsGenerator, EnrollmentManager
)
from auth import get_current_user, require_admin_user
from config import get_settings

settings = get_settings()

# Initialize FastAPI app
app = FastAPI(
    title="Parallel Exam System",
    description="A scalable exam system with parallel processing capabilities",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    try:
        await init_database()
        print("✅ Database initialized successfully")
        print(f"🚀 {settings.app_name} is running!")
        print(f"📚 API documentation: http://localhost:8000/docs")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    await close_database()
    print("🛑 Application shutdown complete")


# Root endpoint
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "parallel-exam-system"}


# Exam Management Endpoints
@app.post("/api/v1/exams", response_model=Exam, tags=["Exams"])
async def create_exam(
    exam_request: CreateExamRequest,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(require_admin_user)
):
    """Create a new exam with questions."""
    try:
        exam_manager = ExamManager(db)
        exam = await exam_manager.create_exam(exam_request)
        return exam
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/exams", response_model=List[Exam], tags=["Exams"])
async def list_exams(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session)
):
    """List all exams."""
    exam_manager = ExamManager(db)
    exams = await exam_manager.list_exams(skip=skip, limit=limit)
    return exams


@app.get("/api/v1/exams/{exam_id}", response_model=Exam, tags=["Exams"])
async def get_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Get a specific exam by ID."""
    exam_manager = ExamManager(db)
    exam = await exam_manager.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@app.put("/api/v1/exams/{exam_id}/activate", tags=["Exams"])
async def activate_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Activate an exam for taking."""
    exam_manager = ExamManager(db)
    success = await exam_manager.activate_exam(exam_id)
    if not success:
        raise HTTPException(status_code=404, detail="Exam not found")
    return {"message": "Exam activated successfully"}


@app.post("/api/v1/applicants", response_model=Applicant, tags=["Applicants"])
async def register_applicant(
    applicant_request: ApplicantBase,
    db: AsyncSession = Depends(get_db_session)
):
    """Register a new applicant."""
    try:
        applicant_manager = ApplicantManager(db)
        # Check if applicant already exists
        existing = await applicant_manager.get_applicant_by_email(applicant_request.email)
        if existing:
            raise HTTPException(status_code=400, detail="Applicant with this email already exists")
        
        applicant = await applicant_manager.register_applicant(
            applicant_request.name, 
            applicant_request.email, 
            applicant_request.registration_number
        )
        return applicant
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/applicants/{applicant_id}", response_model=Applicant, tags=["Applicants"])
async def get_applicant(
    applicant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Get applicant by ID."""
    applicant_manager = ApplicantManager(db)
    applicant = await applicant_manager.get_applicant(applicant_id)
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    return applicant


@app.get("/api/v1/applicants/email/{email}", response_model=Applicant, tags=["Applicants"])
async def get_applicant_by_email(
    email: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get applicant by email."""
    applicant_manager = ApplicantManager(db)
    applicant = await applicant_manager.get_applicant_by_email(email)
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    return applicant


# Exam Enrollment Endpoints
@app.post("/api/v1/exams/{exam_id}/enrollments", status_code=201, tags=["Enrollments"])
async def enroll_applicants_in_exam(
    exam_id: uuid.UUID,
    enrollment_request: BulkEnrollRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Enroll one or more applicants in an exam."""
    try:
        enrollment_manager = EnrollmentManager(db)
        count = await enrollment_manager.enroll_applicants(exam_id, enrollment_request.applicant_ids)
        return {"message": f"Successfully enrolled {count} applicants."}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/api/v1/exams/{exam_id}/enrollments", response_model=List[Applicant], tags=["Enrollments"])
async def get_enrolled_applicants(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Get a list of all applicants enrolled in an exam."""
    enrollment_manager = EnrollmentManager(db)
    applicants = await enrollment_manager.get_enrolled_applicants(exam_id)
    if not applicants:
        # Returning 200 with an empty list is standard REST practice
        return []
    return applicants

# Exam Session Endpoints
@app.post("/api/v1/exams/{exam_id}/start-all", status_code=200, tags=["Sessions"])
async def start_all_sessions_for_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Starts the exam for all enrolled applicants simultaneously.
    This is an administrative action.
    """
    try:
        session_manager = ExamSessionManager(db)
        count = await session_manager.start_sessions_for_all_enrolled(exam_id)
        return {"message": f"Successfully started sessions for {count} applicants."}
    except (PermissionError, ValueError) as e:
        raise HTTPException(status_code=409, detail=str(e)) # 409 Conflict
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.post("/api/v1/sessions/{session_id}/responses", response_model=ApplicantResponse, tags=["Sessions"])
async def submit_response(
    session_id: uuid.UUID,
    response_data: ResponseSubmission,
    db: AsyncSession = Depends(get_db_session)
):
    """Submit a response to a question."""
    try:
        session_manager = ExamSessionManager(db)
        response = await session_manager.submit_response(session_id, response_data.question_id, response_data.answer)
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/v1/sessions/{session_id}/end", tags=["Sessions"])
async def end_exam_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """End an exam session."""
    session_manager = ExamSessionManager(db)
    success = await session_manager.end_exam_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Exam session ended successfully"}


@app.get("/api/v1/sessions/{session_id}/responses", response_model=List[ApplicantResponse], tags=["Sessions"])
async def get_session_responses(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Get all responses for a session."""
    session_manager = ExamSessionManager(db)
    responses = await session_manager.get_session_responses(session_id)
    return responses


# Evaluation Endpoints
@app.post("/api/v1/evaluations/evaluate-exam", response_model=MPIJobResult, tags=["Evaluation"])
async def evaluate_exam(
    evaluation_request: EvaluateExamRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db_session)
):
    """Evaluate all responses for an exam using parallel processing."""
    try:
        if evaluation_request.parallel_processes < 1 or evaluation_request.parallel_processes > 16:
            raise HTTPException(
                status_code=400, 
                detail="Number of processes must be between 1 and 16"
            )
        
        evaluator = Evaluator(db)
        
        # This triggers the parallel evaluation as a background task
        result = await evaluator.evaluate_exam(
            exam_id=evaluation_request.exam_id,
            num_processes=evaluation_request.parallel_processes
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# Reports and Statistics Endpoints
@app.get("/api/v1/reports/exam-stats/{exam_id}", response_model=ExamStatsResponse, tags=["Reports"])
async def get_exam_statistics(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(require_admin_user)
):
    """Get comprehensive exam statistics."""
    try:
        reports_generator = ReportsGenerator(db)
        stats = await reports_generator.generate_exam_stats(exam_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# System Information Endpoints
@app.get("/api/v1/system/info", tags=["System"])
async def get_system_info():
    """Get system configuration and status."""
    return {
        "app_name": settings.app_name,
        "debug_mode": settings.debug,
        "mpi_processor_path": settings.mpi_processor_path,
        "database_connected": True,  # In real implementation, check actual connection
        "supported_operations": {
            "max_parallel_processes": 16,
            "supported_question_types": ["multiple_choice", "true_false", "short_answer", "essay"],
            "max_exam_duration": 300  # minutes
        }
    }


# Just an example of a protected route for any logged-in user
@app.get("/api/v1/system/me", tags=["System"])
async def get_my_info(user: dict = Depends(get_current_user)):
    """Get authenticated user's information from their token."""
    return {"user_info": user}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    ) 