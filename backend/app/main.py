from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import auth, orders, restaurants

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Food Delivery API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your frontend's origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(restaurants.router)
app.include_router(orders.router)
app.include_router(auth.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Food Delivery API"}
