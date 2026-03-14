import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.v1 import auth, sellers, marketplaces, dashboard, sync, amazon_auth, ai_assistant, ai_reports
from app.services.scheduler import start_scheduler, shutdown_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting RetailSutra backend")
    # Create DynamoDB tables if they don't exist
    try:
        from app.dynamo.tables import create_all_tables
        create_all_tables()
    except Exception as e:
        logger.warning("DynamoDB table creation: %s", e)
    start_scheduler()
    yield
    shutdown_scheduler()
    logger.info("Shutting down RetailSutra backend")


app = FastAPI(title="RetailSutra", version="0.1.0", lifespan=lifespan)

allowed_origins = [settings.FRONTEND_URL, "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(sellers.router, prefix="/api/v1")
app.include_router(marketplaces.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(amazon_auth.router, prefix="/api/v1")
app.include_router(ai_assistant.router, prefix="/api/v1")
app.include_router(ai_reports.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
