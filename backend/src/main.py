from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import health, generate, qa

app = FastAPI(title="Wiki Generator API")

# CORS - allow frontend to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Will be tightened later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(generate.router)
app.include_router(qa.router)


@app.get("/")
def root():
    return {"status": "running", "service": "wiki-generator"}
