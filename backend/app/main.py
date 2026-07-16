from fastapi import FastAPI
from app.database import engine, Base
from app.routes.complaint_routes import router as complaint_router


from fastapi.middleware.cors import CORSMiddleware
#import models
from app.models.user import User
from app.models.department import Department
from app.models.complaint import Complaint
from app.routes.admin_routes import router as admin_router
from app.routes.user_routes import router as user_router
from fastapi.staticfiles import StaticFiles
from app.routes.dashboard_routes import router as dashboard_router
from app.routes import department_routes



#create al tables
Base.metadata.create_all(bind=engine)

app=FastAPI(
    title="CivicFlow AI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads"
)

app.include_router(user_router)
app.include_router(complaint_router)
app.include_router(dashboard_router)
app.include_router(admin_router)
app.include_router(department_routes.router)


@app.get("/")
def home():
    return {
        "message": "Welcome to CivicFlow AI Backend",
        "status":"Running Successfully"
    }