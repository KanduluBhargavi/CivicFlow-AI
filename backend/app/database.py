from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

#load environment variables 
load_dotenv()
DATABASE_URL=os.getenv("DATABASE_URL")

#create database engine
engine=create_engine(DATABASE_URL)

#session for database operations 
SessionLocal=sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

#base class for models
Base=declarative_base()

