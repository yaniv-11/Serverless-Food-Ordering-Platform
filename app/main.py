import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from . import seed
from .database import Base, engine
from .notifications import signup_digest_loop
from .routers import admin, auth, mcp, orders, restaurants, webhooks

logging.basicConfig(level=logging.INFO)

Base.metadata.create_all(bind=engine)

AUTO_SEED = os.getenv("AUTO_SEED", "true").lower() == "true"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if AUTO_SEED:
        seed.run()
    digest_task = asyncio.create_task(signup_digest_loop())
    yield
    digest_task.cancel()


app = FastAPI(title="Foodie API (local replica)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(restaurants.router)
app.include_router(orders.router)
app.include_router(auth.router)
app.include_router(webhooks.router)
app.include_router(mcp.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Foodie API (local replica)"}
