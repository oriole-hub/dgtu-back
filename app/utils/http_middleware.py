import logging

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("app.http")


async def error_middleware(req: Request, call_next):
    try:
        return await call_next(req)
    except Exception:
        log.exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "msg": "Internal server error"},
        )
