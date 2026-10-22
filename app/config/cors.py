import os

from dotenv import load_dotenv

load_dotenv()
DEFAULT_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
def get_allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS")

    if not raw:
        return list(DEFAULT_ORIGINS)

    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]

    if "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS must list explicit origins; '*' is not allowed"
        )

    return origins