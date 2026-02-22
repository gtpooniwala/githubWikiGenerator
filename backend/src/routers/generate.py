from fastapi import APIRouter, Depends

from auth import require_api_key

router = APIRouter(prefix="/api")


@router.post("/generate")
def generate(repo_url: str, _: None = Depends(require_api_key)):
    """Stub endpoint — real pipeline implemented in later steps."""
    return {
        "repo_url": repo_url,
        "status": "stub",
        "message": "Real implementation coming soon",
    }
