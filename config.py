from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: str = ""
    DATABASE_URL: str
    TIMEZONE: str = "Europe/Moscow"
    EXPORT_CHAT_ID: Optional[int] = None
    EXPORT_HOUR: int = 11
    EXPORT_MINUTE: int = 39
    GOOGLE_CREDENTIALS_PATH: Optional[str] = None  # path to service account JSON
    GOOGLE_SPREADSHEET_ID: Optional[str] = None    # Google Sheets document ID

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def admin_ids_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()
