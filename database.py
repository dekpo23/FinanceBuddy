import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()


# Construct Database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Ensure we use the 'psycopg' (v3) driver for SQLAlchemy if it's not specified
# SQLAlchemy defaults 'postgresql://' to 'psycopg2' (which we don't have)
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True  # Good practice to handle stale connections
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


