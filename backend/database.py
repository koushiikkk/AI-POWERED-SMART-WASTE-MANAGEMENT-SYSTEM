import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Select Database Type: 'mysql' or 'supabase'
DATABASE_TYPE = os.getenv("DATABASE_TYPE", "mysql").lower()

if DATABASE_TYPE == "supabase":
    # Supabase PostgreSQL Configuration
    db_user = os.getenv("SUPABASE_DB_USER", "postgres")
    db_pass = os.getenv("SUPABASE_DB_PASSWORD", "")
    db_host = os.getenv("SUPABASE_DB_HOST", "localhost")
    db_port = os.getenv("SUPABASE_DB_PORT", "5432")
    db_name = os.getenv("SUPABASE_DB_NAME", "postgres")
    
    # Direct DATABASE_URL override if available
    default_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    DATABASE_URL = os.getenv("DATABASE_URL", default_url)
    print(f"[DB INFO] Initialized SQLAlchemy Engine for Option B: Supabase (PostgreSQL)")
else:
    # Local MySQL Configuration (Default)
    db_user = os.getenv("MYSQL_USER", "root")
    db_pass = os.getenv("MYSQL_PASSWORD", "")
    db_host = os.getenv("MYSQL_HOST", "127.0.0.1")
    db_port = os.getenv("MYSQL_PORT", "3306")
    db_name = os.getenv("MYSQL_DATABASE", "exam_db")
    
    default_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    DATABASE_URL = os.getenv("DATABASE_URL", default_url)
    print(f"[DB INFO] Initialized SQLAlchemy Engine for Option A: Local MySQL")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI Dependency for Database Sessions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
