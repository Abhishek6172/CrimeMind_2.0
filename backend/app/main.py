import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, errors
from .routers import analysis, auth, authoring, cases, insights, oversight, cctv, nlp, advanced_ml
from .research.routes import router as research_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="CrimeMind API", version=config.APP_VERSION,
              description="AI-assisted criminal investigation decision support (synthetic data).")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["x-request-id"])
errors.install(app)
for r in (auth.router, cases.router, authoring.router, insights.router, analysis.router, oversight.router, cctv.router, nlp.router, advanced_ml.router, research_router):
    app.include_router(r)


@app.on_event("startup")
def _startup():
    db.init_pool()


@app.on_event("shutdown")
def _shutdown():
    db.close_pool()


@app.get("/api/health")
def health():
    try:
        with db.connection() as c:
            c.execute("SELECT 1")
        return {"status": "ok", "database": "up", "version": config.APP_VERSION}
    except Exception:
        return {"status": "degraded", "database": "down", "version": config.APP_VERSION}
