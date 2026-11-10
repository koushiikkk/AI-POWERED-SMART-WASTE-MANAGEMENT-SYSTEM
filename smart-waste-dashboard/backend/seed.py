import os
import mysql.connector
import bcrypt
from dotenv import load_dotenv

load_dotenv()

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def run_migration_and_seed():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "smart_waste_db"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    
    cursor = conn.cursor()

    # 1. Run Migration (Skipped because it ran partially, but let's try/except)
    migration_path = os.path.join(os.path.dirname(__file__), "..", "database", "users_migration.sql")
    with open(migration_path, 'r') as f:
        sql_script = f.read()
        
    for statement in sql_script.split(';'):
        if statement.strip():
            print(f"Executing: {statement.strip()[:50]}...")
            try:
                cursor.execute(statement)
            except mysql.connector.errors.ProgrammingError as e:
                print(f"Skipping (likely already exists): {e}")
            
    conn.commit()

    # 2. Seed Users
    users = [
        ("citizen", get_password_hash("citizen123"), "CITIZEN"),
        ("staff", get_password_hash("staff123"), "STAFF"),
        ("admin", get_password_hash("admin123"), "ADMIN"),
    ]
    
    for username, hashed_pw, role in users:
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, hashed_pw, role)
            )
        except mysql.connector.errors.IntegrityError:
            print(f"User {username} already exists.")
            pass
            
    conn.commit()
    cursor.close()
    conn.close()
    print("Migration and seed complete.")

if __name__ == "__main__":
    run_migration_and_seed()
