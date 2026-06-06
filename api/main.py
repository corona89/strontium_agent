from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.connection import Base, engine
import database.models  # noqa: F401 — 모델을 Base에 등록
from routers import account


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(account.router)


@app.get("/")
def read_root():
    return {"message": "Where Winds Meet API"}
