import json
import subprocess
import asyncio
import tempfile
import os
import platform
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid

from models import MPIJobConfig, MPIJobResult, ApplicantResponse, Question
from config import get_settings

settings = get_settings()


class MPICoordinator:
    """Coordinates MPI parallel processing for exam evaluation."""
    
    def __init__(self):
        self.settings = get_settings()
        self.mpi_processor_command = self.settings.mpi_processor_path
        self.temp_dir = Path(tempfile.gettempdir()) / "parallel_exam_system"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Determine if using Python simulator
        self.use_python_simulator = "python" in self.mpi_processor_command.lower()
    
    async def evaluate_responses_parallel(
        self,
        responses: List[ApplicantResponse],
        questions: List[Question],
        num_processes: int = 4
    ) -> MPIJobResult:
        """
        Evaluate exam responses using parallel MPI processing.
        
        Args:
            responses: List of applicant responses to evaluate
            questions: List of questions with correct answers
            num_processes: Number of MPI processes to use
            
        Returns:
            MPIJobResult with evaluation results
        """
        job_id = uuid.uuid4()
        start_time = datetime.utcnow()
        
        try:
            # Prepare input data
            input_data = self._prepare_input_data(responses, questions)
            
            # Create temporary files
            input_file = self.temp_dir / f"input_{job_id}.json"
            output_file = self.temp_dir / f"output_{job_id}.json"
            
            # Write input data
            with open(input_file, 'w') as f:
                json.dump(input_data, f, indent=2, default=str)
            
            # Create MPI job configuration
            config = MPIJobConfig(
                num_processes=num_processes,
                input_file=str(input_file),
                output_file=str(output_file),
                timeout_seconds=300
            )
            
            # Execute MPI job
            success = await self._execute_mpi_job(config)
            
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            if success and output_file.exists():
                # Read results
                with open(output_file, 'r') as f:
                    output_data = json.load(f)
                
                result = MPIJobResult(
                    job_id=job_id,
                    config=config,
                    status="completed",
                    start_time=start_time,
                    end_time=end_time,
                    execution_time_seconds=execution_time,
                    output_data=output_data
                )
            else:
                result = MPIJobResult(
                    job_id=job_id,
                    config=config,
                    status="failed",
                    start_time=start_time,
                    end_time=end_time,
                    execution_time_seconds=execution_time,
                    error_message="MPI job execution failed"
                )
            
            # Cleanup temporary files
            self._cleanup_temp_files([input_file, output_file])
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            return MPIJobResult(
                job_id=job_id,
                config=MPIJobConfig(
                    num_processes=num_processes,
                    input_file="",
                    output_file="",
                    timeout_seconds=300
                ),
                status="error",
                start_time=start_time,
                end_time=end_time,
                execution_time_seconds=execution_time,
                error_message=str(e)
            )
    
    def _prepare_input_data(
        self, 
        responses: List[ApplicantResponse], 
        questions: List[Question]
    ) -> Dict[str, Any]:
        """Prepare input data for MPI processing."""
        
        # Create question lookup dictionary
        question_dict = {str(q.id): q for q in questions}
        
        # Prepare evaluation tasks
        evaluation_tasks = []
        for response in responses:
            question = question_dict.get(str(response.question_id))
            if question:
                task = {
                    "response_id": str(response.id),
                    "session_id": str(response.session_id),
                    "question_id": str(response.question_id),
                    "applicant_answer": response.answer,
                    "correct_answer": question.correct_answer,
                    "question_type": question.question_type,
                    "points": question.points,
                    "options": question.options or []
                }
                evaluation_tasks.append(task)
        
        return {
            "job_metadata": {
                "total_tasks": len(evaluation_tasks),
                "total_responses": len(responses),
                "total_questions": len(questions),
                "timestamp": datetime.utcnow().isoformat()
            },
            "evaluation_tasks": evaluation_tasks
        }
    
    async def _execute_mpi_job(self, config: MPIJobConfig) -> bool:
        """Execute the MPI job using subprocess."""
        try:
            # Construct command based on processor type
            if self.use_python_simulator:
                # Python simulator command
                command_parts = self.mpi_processor_command.split()
                mpi_command = command_parts + [
                    config.input_file,
                    config.output_file,
                    str(config.num_processes)
                ]
                print(f"Using Python simulator: {' '.join(mpi_command)}")
            else:
                # Check if MPI processor exists
                processor_path = Path(self.mpi_processor_command)
                if not processor_path.exists():
                    print(f"Warning: MPI processor not found at {processor_path}")
                    # Fall back to simulation
                    return await self._simulate_mpi_processing(config)
                
                # Native MPI command
                mpi_command = [
                    "mpirun" if not platform.system() == "Windows" else "mpiexec",
                    "--allow-run-as-root",
                    "-n", str(config.num_processes),
                    str(processor_path),
                    config.input_file,
                    config.output_file
                ]
                print(f"Using native MPI: {' '.join(mpi_command)}")
            
            print(f"Executing MPI command: {' '.join(mpi_command)}")
            
            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                *mpi_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=config.timeout_seconds
                )
                
                if process.returncode == 0:
                    print("MPI job completed successfully")
                    return True
                else:
                    print(f"MPI job failed with return code {process.returncode}")
                    print(f"stderr: {stderr.decode()}")
                    return False
                    
            except asyncio.TimeoutError:
                process.kill()
                print("MPI job timed out")
                return False
                
        except Exception as e:
            print(f"Error executing MPI job: {e}")
            return False
    
    async def _simulate_mpi_processing(self, config: MPIJobConfig) -> bool:
        """Simulate MPI processing for MVP demonstration."""
        try:
            print("Simulating MPI processing (MPI processor not available)")
            
            # Read input data
            with open(config.input_file, 'r') as f:
                input_data = json.load(f)
            
            evaluation_tasks = input_data.get("evaluation_tasks", [])
            
            # Simulate parallel evaluation
            results = []
            for task in evaluation_tasks:
                # Simple evaluation logic
                is_correct = self._evaluate_answer(
                    task["applicant_answer"],
                    task["correct_answer"],
                    task["question_type"]
                )
                
                points_earned = task["points"] if is_correct else 0
                
                result = {
                    "response_id": task["response_id"],
                    "session_id": task["session_id"],
                    "question_id": task["question_id"],
                    "is_correct": is_correct,
                    "points_earned": points_earned,
                    "evaluation_time": datetime.utcnow().isoformat()
                }
                results.append(result)
            
            # Simulate processing time
            await asyncio.sleep(0.1 * len(evaluation_tasks) / config.num_processes)
            
            # Write output data
            output_data = {
                "job_metadata": {
                    "processed_tasks": len(results),
                    "simulation": True,
                    "processes_used": config.num_processes,
                    "completion_time": datetime.utcnow().isoformat()
                },
                "evaluation_results": results
            }
            
            with open(config.output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            print(f"Simulated evaluation of {len(results)} tasks completed")
            return True
            
        except Exception as e:
            print(f"Error in simulated MPI processing: {e}")
            return False
    
    def _evaluate_answer(
        self, 
        applicant_answer: str, 
        correct_answer: str, 
        question_type: str
    ) -> bool:
        """Simple answer evaluation logic."""
        applicant_answer = applicant_answer.strip().lower()
        correct_answer = correct_answer.strip().lower()
        
        if question_type == "multiple_choice":
            return applicant_answer == correct_answer
        elif question_type == "true_false":
            return applicant_answer == correct_answer
        elif question_type == "short_answer":
            # Simple string matching (in real implementation, use fuzzy matching)
            return applicant_answer == correct_answer
        else:
            # For essay questions, would need more sophisticated evaluation
            return len(applicant_answer) > 10  # Simple length check
    
    def _cleanup_temp_files(self, files: List[Path]):
        """Clean up temporary files."""
        for file_path in files:
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                print(f"Warning: Could not delete temporary file {file_path}: {e}")
    
    def get_job_status(self, job_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get status of a running MPI job."""
        # In a real implementation, this would track running jobs
        # For MVP, return None (job tracking not implemented)
        return None
    
    async def cancel_job(self, job_id: uuid.UUID) -> bool:
        """Cancel a running MPI job."""
        # In a real implementation, this would cancel running jobs
        # For MVP, return False (job cancellation not implemented)
        return False 