"""Q&A endpoint — answer questions about a repo using the generated wiki as context.

The full wiki (overview + all feature pages) fits comfortably in gpt-5-mini's
128k context window (typically 3–8k tokens), so we pass it all in one call
rather than doing retrieval.  This gives the LLM cross-page awareness and
keeps the implementation simple.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import require_api_key
from models.schemas import QARequest, QAResponse
from services import llm

router = APIRouter(prefix="/api")

_SYSTEM = """\
You are an expert assistant answering questions about a software repository \
based on its auto-generated wiki documentation.

The wiki you have been given contains:
- An Overview page explaining what the project does, its architecture, and \
  how to run it.
- Feature pages, one per user-facing feature, each with implementation \
  details and inline citations linking to the source code.

Answer the user's question accurately and concisely.  Where relevant, \
reference specific feature names or sections from the wiki.  If the wiki \
does not contain enough information to answer the question confidently, say so \
rather than guessing.  Keep answers to 2–5 short paragraphs.
"""

# Hard limit on how large the wiki context can grow before we truncate.
# gpt-5-mini supports 400k tokens; 80k chars ≈ 20k tokens — well within limit.
_MAX_CONTEXT_CHARS = 80_000


def _build_user_message(body: QARequest) -> str:
    """Assemble the wiki context + question as the user message."""
    parts: list[str] = [f"# Wiki for {body.repo_id}\n"]

    parts.append("## Overview\n")
    parts.append(body.overview_md.strip())

    for feature in body.features:
        parts.append(f"\n\n## {feature.title}\n")
        if feature.description:
            parts.append(f"_{feature.description}_\n")
        parts.append(feature.content_md.strip())

    wiki_block = "\n".join(parts)

    # Truncate gracefully if the wiki is unusually large
    if len(wiki_block) > _MAX_CONTEXT_CHARS:
        wiki_block = (
            wiki_block[:_MAX_CONTEXT_CHARS] + "\n\n[...wiki truncated due to length...]"
        )

    return f"{wiki_block}\n\n---\n\nQuestion: {body.question}"


@router.post("/qa", response_model=QAResponse)
def qa(body: QARequest, _: None = Depends(require_api_key)) -> QAResponse:
    """Answer a question about a repo using its generated wiki as context.

    The complete wiki (overview + feature pages) is passed as context in a
    single LLM call.  No retrieval step is needed because the full wiki
    fits well within the model's context window.
    """
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="question must not be empty")

    user_message = _build_user_message(body)

    try:
        answer = llm.chat_text(_SYSTEM, user_message, temperature=0.3)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return QAResponse(answer=answer)
