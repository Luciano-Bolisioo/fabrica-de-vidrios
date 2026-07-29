from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    google_sheet_id: str = "1KW8Q1YUzijV9uFmQj-x5ZMwxkCMC1rBZzt2HiVCOlYE"
    api_base_url: str = "http://127.0.0.1:8000"

    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: str = ""  # "123,456" o vacío = todos

    uploads_dir: Path = ROOT_DIR / "data" / "uploads"
    okf_dir: Path = ROOT_DIR / "data" / "okf"
    okf_documents_dir: Path = ROOT_DIR / "data" / "okf" / "documents"

    def allowed_telegram_chat_ids(self) -> set[int]:
        raw = (self.telegram_allowed_chat_ids or "").strip()
        if not raw:
            return set()
        ids: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if part:
                ids.add(int(part))
        return ids


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.okf_documents_dir.mkdir(parents=True, exist_ok=True)
    return settings
