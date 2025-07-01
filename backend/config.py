import os
import platform
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Database settings from environment variables
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    
    # Supabase settings (can be empty if using local DB)
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    
    # Secret key for JWT or other security features
    secret_key: str = os.getenv("SECRET_KEY", "a-very-secret-key-that-should-be-changed")
    
    # MPI processor path is now set via docker-compose environment variable
    mpi_processor_path: str = os.getenv("MPI_PROCESSOR_PATH", "/app/mpi_processor/evaluator")
    
    # Application metadata
    app_name: str = "Parallel Exam System"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    class Config:
        # Load environment variables from a .env file if it exists
        env_file = ".env"
        env_file_encoding = 'utf-8'

@lru_cache()
def get_settings():
    """Get cached settings instance."""
    return Settings() 