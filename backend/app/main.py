from fastapi import FastAPI

app = FastAPI(
    title="Codebase AI",
    description="AI-powered software project knowledge assistant",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "codebase-ai-api",
    }
