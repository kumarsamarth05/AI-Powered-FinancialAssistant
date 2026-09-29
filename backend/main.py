import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

load_dotenv()

from backend.db.mongo import close_client, create_indexes, ping_database
from backend.demo_data import ensure_demo_data
from backend.routes import alerts, analyze, auth, chat, demo, forecast, goals, history, imports, live, risk, transactions

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Financial Assistant")
    db_ok = await ping_database()
    app.state.database_available = db_ok
    if db_ok:
        try:
            await create_indexes()
        except Exception as exc:
            logger.warning(f"Could not create all MongoDB indexes: {exc}")

        if os.getenv("AUTO_SEED_DEMO", "true").lower() in {"1", "true", "yes", "on"}:
            try:
                result = await ensure_demo_data()
                if result.get("refreshed"):
                    logger.info(
                        f"Demo data refreshed: {result.get('current_month_transactions')} "
                        f"current-month debit transaction(s), total={result.get('current_month_total')}"
                    )
            except Exception as exc:
                logger.warning(f"Could not ensure demo data: {exc}")
    else:
        logger.warning("MongoDB is unavailable. Database-backed endpoints will fail until MongoDB is running.")
    yield
    await close_client()
    logger.info("Server shut down")


app = FastAPI(
    title="AI Financial Assistant",
    description="NLP Powered Personal Finance Analytics Platform",
    version="1.3.0",
    lifespan=lifespan,
)

raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
if ENVIRONMENT == "development" and os.getenv("ALLOW_ALL_ORIGINS", "false").lower() in {"1", "true", "yes"}:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(f"{request.method} {request.url.path} Status={response.status_code} Time={elapsed_ms}ms")
    return response


@app.get("/health", tags=["System"])
async def health():
    database = await ping_database()
    return {
        "status": "healthy" if database else "degraded",
        "environment": ENVIRONMENT,
        "database": "connected" if database else "unavailable",
        "version": app.version,
    }


app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(analyze.router, prefix="/analyze", tags=["Analytics"])
app.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
app.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
app.include_router(history.router, prefix="/history", tags=["History"])
app.include_router(imports.router, prefix="/imports", tags=["Imports"])
app.include_router(goals.router, prefix="/goals", tags=["Goals"])
app.include_router(risk.router, prefix="/risk", tags=["Risk"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(forecast.router, prefix="/forecast", tags=["Forecast"])
app.include_router(live.router, prefix="/live", tags=["Live Analytics"])
app.include_router(demo.router, prefix="/demo", tags=["Demo Tools"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"success": False, "message": "Internal Server Error"})


# Mount a frontend only when it is actually present. This keeps a backend-only ZIP runnable.
project_root = Path(__file__).resolve().parent.parent
frontend_dir = project_root / "frontend"
if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    @app.get("/", tags=["System"])
    async def root():
        return {
            "name": "AI Financial Assistant API",
            "status": "running",
            "docs": "/docs",
            "health": "/health",
        }
