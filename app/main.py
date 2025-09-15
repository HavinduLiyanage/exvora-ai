import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.routes import router
from app.api.admin import router as admin_router
from app.api.rerank import router as rerank_router
from app.api.ai_rerank import router as ai_rerank_router

from app.api.errors import error_response
import uuid
import time
import logging
# from app.api import rerank as rerank_module
from app.api import ai_rerank as rerank_module
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.req_id = request_id
        
        # Log request start
        start_time = time.time()
        logger.info(f"[{request_id}] {request.method} {request.url.path} started")
        
        # Process request
        response = await call_next(request)
        
        # Log request completion
        duration = time.time() - start_time
        logger.info(f"[{request_id}] {request.method} {request.url.path} completed in {duration:.3f}s")
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response



from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

app = FastAPI(title="Exvora Stateless Itinerary API", version="0.1.0")
app.add_middleware(RequestIDMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router, prefix="/v1")
app.include_router(admin_router)
app.include_router(rerank_router, prefix="/v1")
app.include_router(ai_rerank_router, prefix="/v1")

# Serve landing page at root
@app.get("/", response_class=HTMLResponse)
async def landing_page():
    return FileResponse("static/index.html")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with consistent error format."""
    from fastapi.responses import JSONResponse
    error_data = error_response(422, "validation_error", "Request validation failed", [str(error) for error in exc.errors()])
    return JSONResponse(status_code=422, content=error_data)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error format."""
    from fastapi.responses import JSONResponse
    if hasattr(exc.detail, 'get') and callable(exc.detail.get):
        # Already structured error
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    else:
        # Convert simple string to structured format
        error_data = error_response(exc.status_code, "http_error", str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content=error_data)

@app.on_event("startup")
async def startup_tasks():
    # configure model path and backend from env or defaults
    model_path = os.environ.get("SAVED_MODEL_PATH", "saved_model")
    ann_backend = os.environ.get("ANN_BACKEND", None)  # 'faiss' or 'hnsw' or None
    rerank_module.init_model(model_path=model_path, ann_backend=ann_backend)
    logger.info("Rerank module initialized during app startup")

@app.on_event("shutdown")
async def shutdown_tasks():
    # ensure model saved on shutdown
    rerank_module.shutdown_model(save_path=os.environ.get("SAVED_MODEL_PATH", "saved_model"))
    logger.info("Rerank module shutdown complete")