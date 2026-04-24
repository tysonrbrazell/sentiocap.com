"""
SentioCap FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import auth, plans, actuals, investments, dashboard, classify, benchmarks

app = FastAPI(
    title="SentioCap API",
    description="AI-powered expense intelligence platform — RTB/CTB classification, planning, and benchmarking.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

origins = settings.cors_origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(actuals.router, prefix="/api")
app.include_router(investments.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(classify.router, prefix="/api")
app.include_router(benchmarks.router, prefix="/api")

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": "sentiocap-api"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
