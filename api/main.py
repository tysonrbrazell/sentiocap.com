from fastapi import FastAPI

from app.routers import ai, auth, benchmarks, exports, investments, plans

app = FastAPI(title="SentioCap API")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(plans.router, prefix="/api/plans", tags=["plans"])
app.include_router(investments.router, prefix="/api/investments", tags=["investments"])
app.include_router(benchmarks.router, prefix="/api/benchmarks", tags=["benchmarks"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(exports.router, prefix="/api/exports", tags=["exports"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
