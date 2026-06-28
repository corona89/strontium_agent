from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import update

from core.config import settings
from core.limiter import limiter
from core.seed import run_seed
from database.connection import Base, AsyncSessionLocal, engine
import database.models  # noqa: F401 — 모델을 Base에 등록
from database.models import DeepResearchSession
from routers import account, admin, auth, deep_research, llmwiki, models, oauth, roles


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        # 서버 비정상 종료로 갇힌 running 세션 복구 (백그라운드 태스크는 재시작 시 소실)
        await db.execute(
            update(DeepResearchSession)
            .where(DeepResearchSession.status == "running")
            .values(status="approved")
        )
        await db.commit()
        await run_seed(db)
    yield


app = FastAPI(lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account.router)
app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(roles.router)
app.include_router(admin.router)
app.include_router(models.router)
app.include_router(deep_research.router)
app.include_router(llmwiki.router)


@app.get("/")
def read_root():
    return {"message": "Where Winds Meet API"}
