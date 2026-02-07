
import os
from database import engine, get_db
from sqlalchemy import text

# Debug printer
print(f"DATABASE_URL used by engine: {engine.url}")

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print(f"Connection successful! Result: {result.scalar()}")
except Exception as e:
    print(f"Connection failed: {e}")
