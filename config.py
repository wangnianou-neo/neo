import os


API_KEY = os.getenv("OPENROUTER_API_KEY", "")
API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8000"))
PORT = int(os.getenv("PORT", "5000"))
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "local-dev-secret-key")
