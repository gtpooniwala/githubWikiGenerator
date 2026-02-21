from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Wiki Generator API")

API_KEY = os.environ.get("API_KEY", "dev-key-123")

# CORS - allow frontend to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # We'll tighten this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/")
def root():
    return {"status": "running", "service": "wiki-generator"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/api/generate")
def generate(repo_url: str, x_api_key: str = Header(...)):
    verify_api_key(x_api_key)
    return {
        "repo": repo_url,
        "status": "skeleton",
        "message": "Real implementation coming soon",
    }
