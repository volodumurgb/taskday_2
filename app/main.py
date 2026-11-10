from fastapi import FastAPI
from app.auth import router as auth_router
from app.wallet import router as wallet_router

app = FastAPI(title="Co-working Booking API")
app.include_router(auth_router)
app.include_router(wallet_router)

@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}