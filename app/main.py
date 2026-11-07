"""FastAPI application entry point following enterprise template architecture."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin import admin_router
from app.api.cashier import cashier_router
from app.api.cashier.pushback import router as pushback_router
from app.api.deps.system_gate import system_gate
from app.api.store import store_router
from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.database import engine
from app.core.enum.response_enum import RESPONSE_CODE_ENUM
from app.core.exceptions import APP_EXCEPTION
from app.core.logger import logger
from app.core.scheduler import APP_SCHEDULER
from app.core.utils.http_client import (
    close_global_httpx_client
    , create_httpx_client
    , set_global_httpx_client
)
from app.middleware.access import BASE_MIDDLEWARE
from app.middleware.auth import SYSTEM_AUTH_MIDDLEWARE
from app.middleware.trace import TRACE_MIDDLEWARE
from app.schemas.base_schema import RESPONSE_ENVELOPE
from app.services.r2_service import R2_SERVICE


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager handling startup and shutdown hooks:
    - Initializes global pooled httpx.AsyncClient
    - Starts APScheduler
    - Disposes httpx pool, scheduler, and SQLAlchemy engine on shutdown
    """
    try:
        logger.info(
            f"Starting {settings.PROJECT_NAME} ({settings.COMPONENT_NAME}) in [{settings.ENV}] mode..."
        )
        httpx_client           = create_httpx_client()
        app.state.httpx_client = httpx_client
        set_global_httpx_client(httpx_client)
        APP_SCHEDULER.start()

        if settings.ENV not in ("testing", "test"):
            try:
                R2_SERVICE.ensure_bucket_exists()
            except Exception as e:
                logger.warning(f"R2 storage auto-initialization notice: {e}")

        yield
    except Exception as e:
        logger.error(f"Error during application startup: {str(e)}")
        raise
    finally:
        try:
            await close_global_httpx_client()
            APP_SCHEDULER.shutdown()
            engine.dispose()
            logger.info("Application shutdown completed cleanly.")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")


app = FastAPI(
    title         = settings.PROJECT_NAME
    , version     = "1.0.0"
    , description = "Production-grade Clothing Store Management System API"
    , docs_url    = "/api/docs" if settings.ENV != "production" else None
    , redoc_url   = "/api/redoc" if settings.ENV != "production" else None
    , openapi_url = f"{settings.API_V1_STR}/openapi.json" if settings.ENV != "production" else None
    , lifespan    = lifespan
    , dependencies = [Depends(system_gate)]
)


# ── Custom Exception Handlers ─────────────────────────────────────────────────

async def app_exception_handler(request: Request, exc: APP_EXCEPTION) -> JSONResponse:
    request_id      = getattr(request.state, "request_id", None)
    envelope        = RESPONSE_ENVELOPE.error(
        code         = exc.code
        , message    = exc.message
        , errors     = exc.errors
        , request_id = request_id
    )
    payload           = envelope.model_dump()
    payload["detail"] = exc.message
    return JSONResponse(
        status_code = exc.status_code
        , content   = payload
        , headers   = {"X-Request-ID": request_id} if request_id else None
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id      = getattr(request.state, "request_id", None)
    errors          = [f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()]
    envelope        = RESPONSE_ENVELOPE.error(
        code         = RESPONSE_CODE_ENUM.VALIDATION_ERROR
        , message    = "Request payload validation failed."
        , errors     = errors
        , request_id = request_id
    )
    payload           = envelope.model_dump()
    payload["detail"] = exc.errors()
    return JSONResponse(
        status_code = 422
        , content   = payload
        , headers   = {"X-Request-ID": request_id} if request_id else None
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    code       = (
        RESPONSE_CODE_ENUM.UNAUTHORIZED if exc.status_code == 401
        else RESPONSE_CODE_ENUM.FORBIDDEN if exc.status_code == 403
        else RESPONSE_CODE_ENUM.NOT_FOUND if exc.status_code == 404
        else RESPONSE_CODE_ENUM.CONFLICT if exc.status_code == 409
        else RESPONSE_CODE_ENUM.BAD_REQUEST if exc.status_code < 500
        else RESPONSE_CODE_ENUM.INTERNAL_SERVER_ERROR
    )
    envelope          = RESPONSE_ENVELOPE.error(
        code         = code
        , message    = str(exc.detail)
        , errors     = [str(exc.detail)]
        , request_id = request_id
    )
    payload           = envelope.model_dump()
    payload["detail"] = exc.detail
    return JSONResponse(
        status_code = exc.status_code
        , content   = payload
        , headers   = {"X-Request-ID": request_id} if request_id else None
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled error on {request.method} {request.url}: {exc}")
    request_id = getattr(request.state, "request_id", None)
    envelope   = RESPONSE_ENVELOPE.error(
        code         = RESPONSE_CODE_ENUM.INTERNAL_SERVER_ERROR
        , message    = "Internal server error"
        , errors     = [str(exc)]
        , request_id = request_id
    )
    payload           = envelope.model_dump()
    payload["detail"] = "Internal server error"
    return JSONResponse(
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        , content   = payload
        , headers   = {"X-Request-ID": request_id} if request_id else None
    )


app.add_exception_handler(APP_EXCEPTION, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


# ── Middleware Stack Assembly (Outermost -> Innermost: Trace -> CORS -> Auth -> Access)
app.add_middleware(BASE_MIDDLEWARE)
app.add_middleware(SYSTEM_AUTH_MIDDLEWARE)
app.add_middleware(
    CORSMiddleware
    , allow_origins     = settings.WHITE_LIST_CORS
    , allow_credentials = True
    , allow_methods     = ["*"]
    , allow_headers     = ["*"]
)
app.add_middleware(TRACE_MIDDLEWARE)


# ── Static Files & API Routers ────────────────────────────────────────────────
candidate_uploads = [
    os.getenv("UPLOAD_DIR", "/app/uploads"),
    "/app/uploads",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads")),
    os.path.abspath(os.path.join(os.getcwd(), "uploads")),
]
uploads_dir = next((p for p in candidate_uploads if os.path.isdir(p)), None)
if not uploads_dir:
    uploads_dir = "/app/uploads"
    os.makedirs(uploads_dir, exist_ok=True)

logger.info(f"Configuring static uploads path: {uploads_dir}")


@app.get("/uploads/{file_path:path}", tags=["Static Files"])
async def serve_uploads(file_path: str):
    """Serve uploaded media from local disk or stream directly from Cloudflare R2."""
    clean_path = file_path.strip("/\\")
    search_dirs = [uploads_dir, os.path.abspath(settings.UPLOAD_DIR)]
    for d in search_dirs:
        local_target = os.path.join(d, clean_path)
        if os.path.isfile(local_target):
            return FileResponse(local_target)

    # 2. Cloudflare R2 fallback streaming
    if R2_SERVICE.is_configured():
        client = R2_SERVICE.get_client()
        if client:
            candidate_keys = [f"uploads/{clean_path}", clean_path]
            for key in candidate_keys:
                try:
                    obj = client.get_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
                    return StreamingResponse(
                        obj["Body"],
                        media_type=obj.get("ContentType", "application/octet-stream"),
                        headers={"Cache-Control": "public, max-age=86400"},
                    )
                except Exception:
                    pass

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload file not found")

# Unified v1 API Router (/api/v1/*)
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

# Public callback (no auth — ABA posts here)
app.include_router(pushback_router)

# Three dedicated API lanes
app.include_router(admin_router)    # /api/admin/v1/   — Admin & Manager
app.include_router(cashier_router)  # /api/cashier/v1/ — Cashier / POS terminal
app.include_router(store_router)    # /api/store/v1/   — Public web storefront


@app.get("/health", tags=["Health"])
async def root_health_check() -> dict:
    return {"status": "ok", "environment": settings.ENVIRONMENT}
