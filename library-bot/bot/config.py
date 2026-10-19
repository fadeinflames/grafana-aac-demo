import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    token: str
    allowed_users: frozenset[int]
    library_dir: Path
    inpx_file: str | None
    db_path: Path
    default_lang: str
    ebook_convert: str
    ai_search: bool
    ai_model: str
    api_timeout: float
    max_send_bytes: int = 50 * 1024 * 1024  # лимит Bot API на отправку файла

    @staticmethod
    def from_env() -> "Config":
        token = os.environ.get("BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit("BOT_TOKEN не задан")
        users = frozenset(
            int(x) for x in os.environ.get("ALLOWED_USERS", "").replace(" ", "").split(",") if x
        )
        return Config(
            token=token,
            allowed_users=users,
            library_dir=Path(os.environ.get("LIBRARY_DIR", "/srv/library")),
            inpx_file=os.environ.get("INPX_FILE") or None,
            db_path=Path(os.environ.get("DB_PATH", "index.db")),
            default_lang=os.environ.get("DEFAULT_LANG", "").strip().lower(),
            ebook_convert=os.environ.get("EBOOK_CONVERT", "ebook-convert"),
            # ИИ-поиск включён, если есть ключ Anthropic (и не выключен явно AI_SEARCH=0)
            ai_search=bool(os.environ.get("ANTHROPIC_API_KEY")) and os.environ.get("AI_SEARCH", "1") != "0",
            ai_model=os.environ.get("AI_MODEL", "claude-opus-5-5"),
            api_timeout=float(os.environ.get("API_TIMEOUT", "20")),
        )
