from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.auth import router as auth_router
from app.availability import create_cache, router as availability_router
from app.bookings import router as bookings_router
from app.db import engine
from app.wallet import router as wallet_router
from app.locations import router as locations_router
from app.desks import router as desks_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with create_cache() as cache:
        app.state.availability_cache = cache
        try:
            yield
        finally:
            await engine.dispose()


app = FastAPI(title="Co-working Booking API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(wallet_router)
app.include_router(locations_router)
app.include_router(desks_router)
app.include_router(bookings_router)
app.include_router(availability_router)

@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
