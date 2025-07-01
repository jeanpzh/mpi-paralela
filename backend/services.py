from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
import uuid

from models import (
    Question, Exam, Applicant, ExamSession, ApplicantResponse, 
    EvaluationResult, ResultsReport, CreateExamRequest, 
    EvaluateExamRequest, ExamStatsResponse, MPIJobResult, ExamEnrollment
)
from database import (
    QuestionTable, ExamTable, ExamQuestionTable, ApplicantTable,
    ExamSessionTable, ResponseTable, EvaluationTable, ResultsReportTable,
    ExamEnrollmentTable
)
from mpi_coordinator import MPICoordinator


class ExamManager:
    """Manages exam creation, configuration, and lifecycle."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def create_exam(self, exam_request: CreateExamRequest) -> Exam:
        """Create a new exam with questions."""
        # Create exam
        exam_id = uuid.uuid4()
        exam_db = ExamTable(
            id=exam_id,
            title=exam_request.title,
            description=exam_request.description,
            duration_minutes=exam_request.duration_minutes,
            total_questions=len(exam_request.questions),
            total_points=sum(q.points for q in exam_request.questions),
            status="draft"
        )
        
        self.db_session.add(exam_db)
        await self.db_session.flush()
        
        # Create questions first
        questions = []
        question_objects = []
        for i, question_data in enumerate(exam_request.questions):
            question_id = uuid.uuid4()
            question_db = QuestionTable(
                id=question_id,
                content=question_data.content,
                question_type=question_data.question_type,
                options=question_data.options,
                correct_answer=question_data.correct_answer,
                points=question_data.points
            )
            
            self.db_session.add(question_db)
            question_objects.append((question_id, i + 1))
            
            questions.append(Question(
                id=question_id,
                content=question_data.content,
                question_type=question_data.question_type,
                options=question_data.options,
                correct_answer=question_data.correct_answer,
                points=question_data.points,
                created_at=datetime.utcnow()
            ))
        
        # Flush to ensure questions exist before creating relationships
        await self.db_session.flush()
        
        # Now create exam-question relationships
        for question_id, order_number in question_objects:
            exam_question_db = ExamQuestionTable(
                exam_id=exam_id,
                question_id=question_id,
                order_number=order_number
            )
            self.db_session.add(exam_question_db)
        
        await self.db_session.commit()
        
        return Exam(
            id=exam_id,
            title=exam_request.title,
            description=exam_request.description,
            duration_minutes=exam_request.duration_minutes,
            total_questions=len(questions),
            total_points=sum(q.points for q in questions),
            status="draft",
            questions=questions,
            created_at=datetime.utcnow()
        )
    
    async def get_exam(self, exam_id: uuid.UUID) -> Optional[Exam]:
        """Get exam by ID with questions."""
        result = await self.db_session.execute(
            select(ExamTable).where(ExamTable.id == exam_id)
        )
        exam_db = result.scalar_one_or_none()
        
        if not exam_db:
            return None
        
        # Get exam questions
        questions_result = await self.db_session.execute(
            select(QuestionTable)
            .join(ExamQuestionTable)
            .where(ExamQuestionTable.exam_id == exam_id)
            .order_by(ExamQuestionTable.order_number)
        )
        questions_db = questions_result.scalars().all()
        
        questions = [
            Question(
                id=q.id,
                content=q.content,
                question_type=q.question_type,
                options=q.options,
                correct_answer=q.correct_answer,
                points=q.points,
                created_at=q.created_at,
                updated_at=q.updated_at
            )
            for q in questions_db
        ]
        
        return Exam(
            id=exam_db.id,
            title=exam_db.title,
            description=exam_db.description,
            duration_minutes=exam_db.duration_minutes,
            total_questions=exam_db.total_questions,
            total_points=exam_db.total_points,
            status=exam_db.status,
            questions=questions,
            created_at=exam_db.created_at,
            updated_at=exam_db.updated_at
        )
    
    async def list_exams(self, skip: int = 0, limit: int = 100) -> List[Exam]:
        """List all exams."""
        result = await self.db_session.execute(
            select(ExamTable)
            .order_by(ExamTable.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        exams_db = result.scalars().all()
        
        exams = []
        for exam_db in exams_db:
            exam = Exam(
                id=exam_db.id,
                title=exam_db.title,
                description=exam_db.description,
                duration_minutes=exam_db.duration_minutes,
                total_questions=exam_db.total_questions,
                total_points=exam_db.total_points,
                status=exam_db.status,
                questions=[],  # Don't load questions for list view
                created_at=exam_db.created_at,
                updated_at=exam_db.updated_at
            )
            exams.append(exam)
        
        return exams
    
    async def activate_exam(self, exam_id: uuid.UUID) -> bool:
        """Activate an exam for taking."""
        result = await self.db_session.execute(
            update(ExamTable)
            .where(ExamTable.id == exam_id)
            .values(status="active", updated_at=datetime.utcnow())
        )
        await self.db_session.commit()
        return result.rowcount > 0


class ApplicantManager:
    """Manages applicant registration and information."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def register_applicant(self, name: str, email: str, registration_number: Optional[str] = None) -> Applicant:
        """Register a new applicant."""
        applicant_id = uuid.uuid4()
        applicant_db = ApplicantTable(
            id=applicant_id,
            name=name,
            email=email,
            registration_number=registration_number
        )
        
        self.db_session.add(applicant_db)
        await self.db_session.commit()
        
        return Applicant(
            id=applicant_id,
            name=name,
            email=email,
            registration_number=registration_number,
            created_at=datetime.utcnow()
        )
    
    async def get_applicant(self, applicant_id: uuid.UUID) -> Optional[Applicant]:
        """Get applicant by ID."""
        result = await self.db_session.execute(
            select(ApplicantTable).where(ApplicantTable.id == applicant_id)
        )
        applicant_db = result.scalar_one_or_none()
        
        if not applicant_db:
            return None
        
        return Applicant(
            id=applicant_db.id,
            name=applicant_db.name,
            email=applicant_db.email,
            registration_number=applicant_db.registration_number,
            created_at=applicant_db.created_at
        )
    
    async def get_applicant_by_email(self, email: str) -> Optional[Applicant]:
        """Get applicant by email."""
        result = await self.db_session.execute(
            select(ApplicantTable).where(ApplicantTable.email == email)
        )
        applicant_db = result.scalar_one_or_none()
        
        if not applicant_db:
            return None
        
        return Applicant(
            id=applicant_db.id,
            name=applicant_db.name,
            email=applicant_db.email,
            registration_number=applicant_db.registration_number,
            created_at=applicant_db.created_at
        )


class EnrollmentManager:
    """Manages applicant enrollments in exams."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        
    async def enroll_applicants(self, exam_id: uuid.UUID, applicant_ids: List[uuid.UUID]) -> int:
        """Enrolls a list of applicants into a specific exam."""
        
        # 1. Verify that the exam exists and is active
        exam_manager = ExamManager(self.db_session)
        exam = await exam_manager.get_exam(exam_id)
        if not exam:
            raise FileNotFoundError("Exam not found.")
        if exam.status != "active":
            raise PermissionError(f"Cannot enroll applicants. Exam is not active (current status: '{exam.status}').")

        # 2. Prepare enrollments
        enrollments = []
        for applicant_id in applicant_ids:
            enrollment = ExamEnrollmentTable(
                exam_id=exam_id,
                applicant_id=applicant_id
            )
            enrollments.append(enrollment)
        
        self.db_session.add_all(enrollments)
        
        try:
            await self.db_session.commit()
        except IntegrityError:
            await self.db_session.rollback()
            raise ValueError("One or more applicants are already enrolled, or IDs are invalid.")
            
        return len(enrollments)
        
    async def get_enrolled_applicants(self, exam_id: uuid.UUID) -> List[Applicant]:
        """Gets a list of all applicants enrolled in an exam."""
        stmt = (
            select(ApplicantTable)
            .join(ExamEnrollmentTable)
            .where(ExamEnrollmentTable.exam_id == exam_id)
            .order_by(ApplicantTable.name)
        )
        result = await self.db_session.execute(stmt)
        applicants_db = result.scalars().all()
        
        return [Applicant.from_orm(app) for app in applicants_db]

    async def is_applicant_enrolled(self, exam_id: uuid.UUID, applicant_id: uuid.UUID) -> bool:
        """Check if a specific applicant is enrolled in an exam."""
        stmt = (
            select(ExamEnrollmentTable)
            .where(
                ExamEnrollmentTable.exam_id == exam_id,
                ExamEnrollmentTable.applicant_id == applicant_id
            )
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none() is not None


class ExamSessionManager:
    """Manages exam sessions and response submission."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def start_sessions_for_all_enrolled(self, exam_id: uuid.UUID) -> int:
        """
        Starts an exam session for all enrolled applicants simultaneously.
        This is an administrative action.
        """
        # 1. Validate the exam state
        exam_manager = ExamManager(self.db_session)
        exam = await exam_manager.get_exam(exam_id)
        if not exam:
            raise FileNotFoundError("Exam not found.")
        if exam.status != "active":
            raise PermissionError(f"Exam cannot be started. Current status is '{exam.status}'.")

        # 2. Get all enrolled applicants
        enrollment_manager = EnrollmentManager(self.db_session)
        enrolled_applicants = await enrollment_manager.get_enrolled_applicants(exam_id)
        if not enrolled_applicants:
            raise ValueError("No applicants are enrolled in this exam.")
            
        # 3. Create sessions for all of them in a single transaction
        new_sessions = []
        for applicant in enrolled_applicants:
            # Simple check to avoid creating duplicate sessions if run twice by mistake
            existing_session_stmt = select(ExamSessionTable).where(
                ExamSessionTable.exam_id == exam_id,
                ExamSessionTable.applicant_id == applicant.id
            )
            existing_session_result = await self.db_session.execute(existing_session_stmt)
            if existing_session_result.scalar_one_or_none():
                continue # Skip if session already exists for this user

            session_db = ExamSessionTable(
                exam_id=exam_id,
                applicant_id=applicant.id,
                start_time=datetime.utcnow(),
                status="in_progress"
            )
            new_sessions.append(session_db)
        
        if not new_sessions:
            raise ValueError("All enrolled applicants already have a session.")

        self.db_session.add_all(new_sessions)
        
        # 4. Update exam status to 'in_progress'
        exam_table_update_stmt = (
            update(ExamTable)
            .where(ExamTable.id == exam_id)
            .values(status="in_progress", updated_at=datetime.utcnow())
        )
        await self.db_session.execute(exam_table_update_stmt)
        
        await self.db_session.commit()
        
        return len(new_sessions)
    
    async def submit_response(self, session_id: uuid.UUID, question_id: uuid.UUID, answer: str) -> ApplicantResponse:
        """Submit a response to a question."""
        response_id = uuid.uuid4()
        response_db = ResponseTable(
            id=response_id,
            session_id=session_id,
            question_id=question_id,
            answer=answer
        )
        
        self.db_session.add(response_db)
        await self.db_session.commit()
        
        return ApplicantResponse(
            id=response_id,
            session_id=session_id,
            question_id=question_id,
            answer=answer,
            submitted_at=datetime.utcnow()
        )
    
    async def end_exam_session(self, session_id: uuid.UUID) -> bool:
        """End an exam session."""
        result = await self.db_session.execute(
            update(ExamSessionTable)
            .where(ExamSessionTable.id == session_id)
            .values(end_time=datetime.utcnow(), status="completed")
        )
        await self.db_session.commit()
        return result.rowcount > 0
    
    async def get_session_responses(self, session_id: uuid.UUID) -> List[ApplicantResponse]:
        """Get all responses for a session."""
        result = await self.db_session.execute(
            select(ResponseTable).where(ResponseTable.session_id == session_id)
        )
        responses_db = result.scalars().all()
        
        return [
            ApplicantResponse(
                id=r.id,
                session_id=r.session_id,
                question_id=r.question_id,
                answer=r.answer,
                is_correct=r.is_correct,
                points_earned=r.points_earned,
                submitted_at=r.submitted_at
            )
            for r in responses_db
        ]


class Evaluator:
    """Handles exam evaluation using parallel processing."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.mpi_coordinator = MPICoordinator()
    
    async def evaluate_exam(self, exam_id: uuid.UUID, num_processes: int = 4) -> MPIJobResult:
        """Evaluate all responses for an exam using parallel processing."""
        # Get all completed sessions for the exam
        sessions_result = await self.db_session.execute(
            select(ExamSessionTable)
            .where(and_(
                ExamSessionTable.exam_id == exam_id,
                ExamSessionTable.status == "completed"
            ))
        )
        sessions = sessions_result.scalars().all()
        
        if not sessions:
            raise ValueError("No completed sessions found for this exam")
        
        # Get all responses for these sessions
        session_ids = [s.id for s in sessions]
        responses_result = await self.db_session.execute(
            select(ResponseTable)
            .where(ResponseTable.session_id.in_(session_ids))
        )
        responses_db = responses_result.scalars().all()
        
        # Convert to ApplicantResponse objects
        responses = [
            ApplicantResponse(
                id=r.id,
                session_id=r.session_id,
                question_id=r.question_id,
                answer=r.answer,
                is_correct=r.is_correct,
                points_earned=r.points_earned,
                submitted_at=r.submitted_at
            )
            for r in responses_db
        ]
        
        # Get exam questions
        questions_result = await self.db_session.execute(
            select(QuestionTable)
            .join(ExamQuestionTable)
            .where(ExamQuestionTable.exam_id == exam_id)
        )
        questions_db = questions_result.scalars().all()
        
        questions = [
            Question(
                id=q.id,
                content=q.content,
                question_type=q.question_type,
                options=q.options,
                correct_answer=q.correct_answer,
                points=q.points,
                created_at=q.created_at,
                updated_at=q.updated_at
            )
            for q in questions_db
        ]
        
        # Execute parallel evaluation
        mpi_result = await self.mpi_coordinator.evaluate_responses_parallel(
            responses, questions, num_processes
        )
        
        # Store evaluation results
        if mpi_result.status == "completed" and mpi_result.output_data:
            await self._store_evaluation_results(mpi_result.output_data)
        
        return mpi_result
    
    async def _store_evaluation_results(self, output_data: Dict[str, Any]):
        """Store evaluation results in the database."""
        evaluation_results = output_data.get("evaluation_results", [])
        
        # Update responses with evaluation results
        for result in evaluation_results:
            response_id = uuid.UUID(result["response_id"])
            await self.db_session.execute(
                update(ResponseTable)
                .where(ResponseTable.id == response_id)
                .values(
                    is_correct=result["is_correct"],
                    points_earned=result["points_earned"]
                )
            )
        
        # Calculate session scores
        session_scores = {}
        for result in evaluation_results:
            session_id = uuid.UUID(result["session_id"])
            if session_id not in session_scores:
                session_scores[session_id] = {"total_points": 0, "correct_answers": 0}
            
            session_scores[session_id]["total_points"] += result["points_earned"]
            if result["is_correct"]:
                session_scores[session_id]["correct_answers"] += 1
        
        # Store evaluation records
        for session_id, scores in session_scores.items():
            # Get session info
            session_result = await self.db_session.execute(
                select(ExamSessionTable).where(ExamSessionTable.id == session_id)
            )
            session = session_result.scalar_one()
            
            # Get total questions count
            exam_result = await self.db_session.execute(
                select(ExamTable).where(ExamTable.id == session.exam_id)
            )
            exam = exam_result.scalar_one()
            
            score_percentage = (scores["total_points"] / exam.total_points) * 100 if exam.total_points > 0 else 0
            
            evaluation_db = EvaluationTable(
                session_id=session_id,
                total_questions=exam.total_questions,
                correct_answers=scores["correct_answers"],
                total_points=scores["total_points"],
                score_percentage=score_percentage,
                status="completed",
                evaluation_time=datetime.utcnow()
            )
            
            self.db_session.add(evaluation_db)
        
        await self.db_session.commit()


class ReportsGenerator:
    """Generates exam reports and statistics."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def generate_exam_stats(self, exam_id: uuid.UUID) -> ExamStatsResponse:
        """Generate comprehensive exam statistics."""
        # Get basic exam info
        exam_result = await self.db_session.execute(
            select(ExamTable).where(ExamTable.id == exam_id)
        )
        exam = exam_result.scalar_one()
        
        # Get total participants
        total_participants_result = await self.db_session.execute(
            select(func.count(ExamSessionTable.id))
            .where(ExamSessionTable.exam_id == exam_id)
        )
        total_participants = total_participants_result.scalar()
        
        # Get completed sessions
        completed_sessions_result = await self.db_session.execute(
            select(func.count(ExamSessionTable.id))
            .where(and_(
                ExamSessionTable.exam_id == exam_id,
                ExamSessionTable.status == "completed"
            ))
        )
        completed_sessions = completed_sessions_result.scalar()
        
        # Get average score
        avg_score_result = await self.db_session.execute(
            select(func.avg(EvaluationTable.score_percentage))
            .join(ExamSessionTable)
            .where(ExamSessionTable.exam_id == exam_id)
        )
        average_score = avg_score_result.scalar() or 0
        
        # Get score distribution
        scores_result = await self.db_session.execute(
            select(EvaluationTable.score_percentage)
            .join(ExamSessionTable)
            .where(ExamSessionTable.exam_id == exam_id)
        )
        scores = scores_result.scalars().all()
        
        # Create score distribution
        score_distribution = {}
        for score in scores:
            range_key = f"{int(score // 10) * 10}-{int(score // 10) * 10 + 9}"
            score_distribution[range_key] = score_distribution.get(range_key, 0) + 1
        
        return ExamStatsResponse(
            exam_id=exam_id,
            total_participants=total_participants,
            completed_sessions=completed_sessions,
            average_score=float(average_score),
            score_distribution=score_distribution
        ) 