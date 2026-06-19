"""应用配置 — 从环境变量读取，提供合理的开发默认值。"""

from pathlib import Path

from pydantic_settings import BaseSettings


# 项目根目录（src/note_manager/config.py → ../../）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """集中管理所有可配置项。"""

    # 数据库 — 相对路径基于项目根目录解析
    DB_PATH: str = "data/note_manager.db"

    @property
    def db_url(self) -> str:
        """返回完整的 SQLite 连接 URL。"""
        db_path = Path(self.DB_PATH)
        if not db_path.is_absolute():
            db_path = _PROJECT_ROOT / db_path
        # 确保父目录存在
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"

    # JWT
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # 密码
    BCRYPT_ROUNDS: int = 12

    # 路径
    BASE_PATH: str = "/projects/note-manager"

    # 种子数据
    SEED_DEMO: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
