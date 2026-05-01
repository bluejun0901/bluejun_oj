from pathlib import Path
import os


class Settings:
    db_url: str = os.getenv("OJ_DB_URL", "postgresql://oj_user:oj_password@localhost:5432/oj_db")
    redis_url: str = os.getenv("OJ_REDIS_URL", "redis://localhost:6379/0")
    data_dir: Path = Path(os.getenv("OJ_DATA_DIR", "./data")).resolve()
    default_memory_limit_mb: int = int(os.getenv("OJ_MEMORY_LIMIT_MB", "256"))
    isolate_cgroup_mode: str = os.getenv("OJ_ISOLATE_CGROUP", "always").strip().lower()

settings = Settings()
