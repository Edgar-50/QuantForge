from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.api.pro import router as pro_router
from app.db import init_db

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(_):
    init_db()
    yield

app = FastAPI(
    title="QuantForge",
    version="10.0.0",
    description="Quantitative research terminal: market analytics, walk-forward ML forecasting, regime & vol models, portfolio construction, risk, options and strategy lab.",
    lifespan=lifespan,
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(api_router, prefix="/api", tags=["quant"])
app.include_router(pro_router, prefix="/api/v2", tags=["pro"])

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(frontend_dir / "index.html")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "quantforge",
        "version": "10.0.0",
        "modules": [
            "risk","options","portfolio","factor-models","stress-testing",
            "backtesting","walk-forward","volatility","regime-hmm","garch","ml-forecast","screener","hrp","options-iv","simulation","persistence"
        ]
    }
