from pydantic import BaseModel, HttpUrl


class GenerateRequest(BaseModel):
    repo_url: HttpUrl


class WikiFeature(BaseModel):
    id: str
    title: str
    description: str
    content_md: str


class GenerateResponse(BaseModel):
    repo_id: str
    commit_sha: str
    overview_md: str
    features: list[WikiFeature]


class QARequest(BaseModel):
    repo_id: str
    question: str
    overview_md: str
    features: list[WikiFeature]


class QAResponse(BaseModel):
    answer: str
