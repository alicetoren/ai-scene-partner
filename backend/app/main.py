from fastapi import FastAPI


app = FastAPI(title="AI Scene Partner API")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Confirm that the API is available to the frontend."""
    return {"message": "AI Scene Partner backend is running"}
