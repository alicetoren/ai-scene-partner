from fastapi import FastAPI

from app.routes import router
from app.speech_routes import router as speech_router


app = FastAPI(title="AI Scene Partner API")
app.include_router(router)
app.include_router(speech_router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Confirm that the API is available to the frontend."""
    return {"message": "AI Scene Partner backend is running"}
