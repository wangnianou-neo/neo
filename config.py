import os


API_KEY = os.getenv("OPENROUTER_API_KEY", "")
API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "9000"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "240"))
MAX_CONTINUATIONS = int(os.getenv("MAX_CONTINUATIONS", "2"))
PORT = int(os.getenv("PORT", "5000"))
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "local-dev-secret-key")
