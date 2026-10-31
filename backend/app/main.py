from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import PROJECT_NAME, API_V1_STR
from app.modules.datasets.router import router as datasets_router
from app.modules.identity.router import router as identity_router

app = FastAPI(
    title=PROJECT_NAME,
    description="Backend and Database Engineering Services for Chilika Institute of Technology (CIT) Campus Scheduling & Venue Management Platform.",
    version="0.5.0",
    openapi_url=f"{API_V1_STR}/openapi.json",
    docs_url=f"{API_V1_STR}/docs",
    redoc_url=f"{API_V1_STR}/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(datasets_router, prefix=API_V1_STR)
app.include_router(identity_router, prefix=API_V1_STR)


@app.get(f"{API_V1_STR}/health")
def health_check():
    return {
        "status": "healthy",
        "service": PROJECT_NAME,
        "database": "postgresql-15"
    }
