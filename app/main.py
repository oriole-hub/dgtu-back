import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.db import lifespan
from app.routers.auth_routes import auth_router
from app.routers.pass_routes import pass_router
from app.routers.scanner_routes import scanner_router
from app.utils.http_middleware import error_middleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True})


app.middleware("http")(error_middleware)
app.include_router(auth_router)
app.include_router(pass_router)
app.include_router(scanner_router)
