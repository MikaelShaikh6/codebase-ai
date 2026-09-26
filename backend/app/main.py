from fastapi import FastAPI

from app.api.projects import router as projects_router


app = FastAPI(
    title="Codebase AI",
    description="AI-powered software project knowledge assistant",
    version="0.1.0",
)


app.include_router(projects_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "codebase-ai-api",
    }
