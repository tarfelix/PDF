import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings, DEFAULT_BRAND
from services.file_manager import file_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(file_manager.cleanup_loop())
    logger.info("PDF Editor API started")
    yield
    cleanup_task.cancel()
    logger.info("PDF Editor API shutdown")


app = FastAPI(
    title="PDF Editor API",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routes ---
from api.files import router as files_router
from api.merge import router as merge_router
from api.split import router as split_router
from api.extract import router as extract_router
from api.remove import router as remove_router
from api.rotate import router as rotate_router
from api.optimize import router as optimize_router
from api.bates import router as bates_router
from api.redact import router as redact_router
from api.scan import router as scan_router
from api.diff import router as diff_router
from api.converter import router as converter_router
from api.thumbnails import router as thumbnails_router

app.include_router(files_router, prefix="/api")
app.include_router(merge_router, prefix="/api")
app.include_router(split_router, prefix="/api")
app.include_router(extract_router, prefix="/api")
app.include_router(remove_router, prefix="/api")
app.include_router(rotate_router, prefix="/api")
app.include_router(optimize_router, prefix="/api")
app.include_router(bates_router, prefix="/api")
app.include_router(redact_router, prefix="/api")
app.include_router(scan_router, prefix="/api")
app.include_router(diff_router, prefix="/api")
app.include_router(converter_router, prefix="/api")
app.include_router(thumbnails_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/brand")
async def get_brand():
    return DEFAULT_BRAND


# Serve frontend static files (in production)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
