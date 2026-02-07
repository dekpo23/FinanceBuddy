from database import engine, Base
from models import User
from sqlalchemy import text

def reset_users_table():
    print("Dropping users table...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
        conn.commit()
    print("Users table dropped. It will be recreated on next API startup.")

if __name__ == "__main__":
    reset_users_table()
