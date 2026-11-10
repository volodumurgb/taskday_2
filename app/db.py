import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

engine = create_async_engine(os.environ["DATABASE_URL"])
Session = async_sessionmaker(engine)