from fastapi import APIRouter, Depends

from auth import require_api_key
from models.schemas import GenerateRequest, GenerateResponse, WikiFeature

router = APIRouter(prefix="/api")


def _parse_repo_id(repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL."""
    # Works for https://github.com/owner/repo and https://github.com/owner/repo.git
    # Use removesuffix (not rstrip) to avoid stripping individual characters.
    url = str(repo_url).removesuffix("/").removesuffix(".git").removesuffix("/")
    parts = url.split("github.com/")
    if len(parts) != 2:
        raise ValueError(f"Cannot parse repo_id from URL: {repo_url}")
    return parts[1]


@router.post("/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest, _: None = Depends(require_api_key)):
    """Stub endpoint — real pipeline implemented in later steps."""
    repo_id = _parse_repo_id(str(body.repo_url))
    return GenerateResponse(
        repo_id=repo_id,
        commit_sha="stub-sha",
        overview_md=f"# {repo_id}\n\nStub overview — real content coming soon.",
        features=[
            WikiFeature(
                id="stub-feature",
                title="Stub Feature",
                description="This is a stub feature.",
                content_md="Stub content — real wiki pages coming soon.",
            )
        ],
    )
