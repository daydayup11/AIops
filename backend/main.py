from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from logger import setup_logging
from db.sqlite import init_db
from api.chat import router as chat_router
from api.health import router as health_router

setup_logging()

app = FastAPI(title="校园网流量分析助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(health_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
