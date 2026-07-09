from fastapi import FastAPI
from app.database import engine, Base
from app.routes.complaint_routes import router as complaint_router

#import models
from app.models.user import User
from app.models.department import Department
from app.models.complaint import Complaint

from app.routes.user_routes import router as user_router


#create al tables
Base.metadata.create_all(bind=engine)

app=FastAPI(
    title="CivicFlow AI",
    version="1.0.0"
)

app.include_router(user_router)
app.include_router(complaint_router)

@app.get("/")
def home():
    return {
        "message": "Welcome to CivicFlow AI Backend",
        "status":"Running Successfully"
    }