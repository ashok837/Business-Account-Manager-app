import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import models  # noqa: F401  (ensures all model classes are registered with Base)
from auth.auth_utils import limiter
from routers import auth, customers, products, orders, sales, expenses, payments, invoices, reports, dashboard, chat

load_dotenv()

# Schema is managed by Alembic migrations (see backend/alembic/), not by
# auto-creating tables here. Run `alembic upgrade head` once before starting
# the app for the first time (see README - Database setup).

app = FastAPI(
    title="Small Business Management System API",
    description="Multi-tenant REST API for managing customers, products, orders, sales, expenses, payments, invoices and reports.",
    version="2.0.0",
)

# ---------------------------------------------------------------------------
# Rate limiting (brute-force / abuse mitigation). Limits are applied per-route
# with @limiter.limit(...) in routers/auth.py; this wires the shared limiter
# into the app and returns a proper 429 response when a limit is exceeded.
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS: restricted to an explicit allow-list from the environment, not "*".
# Set ALLOWED_ORIGINS in .env to a comma-separated list of your frontend
# URLs (e.g. http://localhost:5173,https://app.yourbusiness.com).
# ---------------------------------------------------------------------------
allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Security headers on every response.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # Only relevant once served over HTTPS (e.g. behind a load balancer in AWS) -
    # harmless over plain HTTP in local development.
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# ---------------------------------------------------------------------------
# Don't leak internal error details (stack traces, SQL, file paths) to clients.
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred. Please try again."})


app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(sales.router)
app.include_router(expenses.router)
app.include_router(payments.router)
app.include_router(invoices.router)
app.include_router(reports.router)
app.include_router(dashboard.router)
app.include_router(chat.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Small Business Management System API. See /docs for API documentation."}
