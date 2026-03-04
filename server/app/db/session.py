import os
import ssl

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from typing import Generator

from app.config import get_settings

settings = get_settings()

connect_args: dict = {}
ca_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "certs", "global-bundle.pem")
if os.path.exists(ca_path):
    connect_args["ssl"] = {"ca": ca_path}

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
