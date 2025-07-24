import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DB_CONFIG, SQLALCHEMY_DATABASE_URL


def get_connection():
    return psycopg2.connect(**DB_CONFIG)



engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Esta es la función que se usa como dependencia
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()