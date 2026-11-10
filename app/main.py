from fastapi import FastAPI

app = FastAPI(title="Co-working Booking API")


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Report that the API process is running."""
    return {"status": "ok"}