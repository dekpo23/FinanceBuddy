import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Construct Database URL from environment variables
DB_USER = os.getenv("db_user", "postgres")
DB_PASSWORD = os.getenv("db_password", "password")
DB_HOST = os.getenv("db_host", "localhost")
DB_PORT = os.getenv("db_port", "5432")
DB_NAME = os.getenv("db_name", "investment_db")

DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


