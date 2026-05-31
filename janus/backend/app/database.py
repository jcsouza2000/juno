from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# DATABASE_URL e obrigatoria em producao (validada em app.config.Settings).
# Em dev, default seguro e SQLite local SEM credenciais hardcoded.
DATABASE_URL = settings.DATABASE_URL

# connect_args so e necessario para SQLite (check_same_thread).
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
