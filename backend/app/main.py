import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.projects import router as projects_router
from app.api.auth import router as auth_router
from app.core.database import create_db_and_tables
from app.services.project_worker import start_project_worker


app = FastAPI(
    title="Codebase AI",
    description="AI-powered software project knowledge assistant",
    version="0.1.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(projects_router)
app.include_router(auth_router)


@app.on_event("startup")
async def startup() -> None:
    create_db_and_tables()
    start_project_worker()


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "codebase-ai-api",
    }
