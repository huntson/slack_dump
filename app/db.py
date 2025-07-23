from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

def make_engine(user, pwd, host, port, name):
    url = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{name}"
    return create_engine(url, future=True, pool_pre_ping=True)

def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
