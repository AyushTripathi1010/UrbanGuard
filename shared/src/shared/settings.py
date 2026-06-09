from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_detect: str = "urbanguard-detect"
    kafka_group_agents: str = "urbanguard-agents"
    kafka_group_rl: str = "urbanguard-rl-feedback"
    kafka_topic_raw_frames: str = "raw-frames"
    kafka_topic_alerts: str = "alerts"
    kafka_topic_rl_feedback: str = "rl-feedback"

    # postgres
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "urbanguard"
    postgres_password: str = "urbanguard"
    postgres_db: str = "urbanguard"

    # redis
    redis_url: str = "redis://localhost:6379/0"

    # minio
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "urbanguard"
    minio_secret_key: str = "urbanguardminio"
    minio_bucket_frames: str = "frames"

    # llm
    llm_primary: str = "gemini"
    llm_fallback: str = "groq"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"

    # langfuse
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3001"

    # routing
    osrm_base_url: str = "http://localhost:5000"

    # mlflow
    mlflow_tracking_uri: str | None = None
    mlflow_tracking_username: str | None = None
    mlflow_tracking_password: str | None = None

    # detection
    detect_device: str = "mps"
    clip_model: str = "ViT-B-32"
    clip_pretrained: str = "laion2b_s34b_b79k"
    clip_accident_threshold: float = 0.35
    resnet_checkpoint: str = "data/checkpoints/resnet50_severity.pt"
    resnet_severity_threshold: float = 0.5

    # ingest
    ingest_target_fps: int = 2
    ingest_data_dir: str = "data/raw"

    # ports
    gateway_port: int = 8000
    ingest_port: int = 8001
    detect_port: int = 8002
    agents_port: int = 8004
    rl_policy_port: int = 8005

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
