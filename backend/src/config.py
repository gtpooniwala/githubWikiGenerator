import os


# Application key used to authenticate frontend → backend requests.
# Must be set via BACKEND_API_KEY env var. No default — missing key means auth always fails.
API_KEY: str = os.environ.get("BACKEND_API_KEY", "")

# OpenAI key — kept server-side only, never exposed to clients
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
