from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, students
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api")
app.include_router(students.router, prefix="/api")
