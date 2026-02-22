import os


# Application key used to authenticate frontend → backend requests
API_KEY: str = os.environ.get("BACKEND_API_KEY", "dev-key-123")

# OpenAI key — kept server-side only, never exposed to clients
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
