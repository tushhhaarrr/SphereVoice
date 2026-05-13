import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)

class EnterpriseAPIError(Exception):
    def __init__(self, status_code: int, message: str, details: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}

class NotFoundError(EnterpriseAPIError):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            status_code=404,
            message=f"{resource_type} with ID {resource_id} not found.",
            details={"resource_type": resource_type, "resource_id": resource_id}
        )

def setup_exception_handlers(app: FastAPI):
    @app.exception_handler(EnterpriseAPIError)
    async def enterprise_api_error_handler(request: Request, exc: EnterpriseAPIError):
        logger.error("api_error", path=request.url.path, status_code=exc.status_code, message=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.status_code,
                    "message": exc.message,
                    "details": exc.details,
                    "type": exc.__class__.__name__
                }
            }
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.status_code,
                    "message": str(exc.detail),
                    "type": "HTTPException"
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": 422,
                    "message": "Validation Error",
                    "details": exc.errors(),
                    "type": "ValidationError"
                }
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": 500,
                    "message": "Internal Server Error",
                    "type": "InternalServerError"
                }
            }
        )
