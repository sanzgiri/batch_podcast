"""Configuration management for Newsletter Podcast Generator."""

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# --- Sub-config models matching what the code accesses ---


class OpenAIConfig(BaseModel):
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    max_tokens: int = 2000
    temperature: float = 0.7


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama2"
    temperature: float = 0.7
    timeout: int = 300
    num_ctx: int = 8192  # context window (input + output tokens)
    num_predict: int = 4096  # max output tokens before truncation


class LLMConfig(BaseModel):
    provider: str = "openai"
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)


class KokoroTTSConfig(BaseModel):
    voice: str = "af_heart"
    lang_code: str = "a"
    speed: float = 1.0
    base_url: str = "http://localhost:8080"


class UnrealSpeechConfig(BaseModel):
    api_key: str = ""
    voice: str = "Liv"
    base_url: str = "https://api.v7.unrealspeech.com"


class TTSConfig(BaseModel):
    provider: str = "kokoro_tts"
    kokoro_tts: KokoroTTSConfig = Field(default_factory=KokoroTTSConfig)
    unreal_speech: UnrealSpeechConfig = Field(default_factory=UnrealSpeechConfig)


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    enable_docs: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class DatabaseConfig(BaseModel):
    url: str = "sqlite+aiosqlite:///./data/newsletter_podcast_dev.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "./logs/app_dev.log"
    max_bytes: int = 10485760
    backup_count: int = 5


class StorageConfig(BaseModel):
    type: str = "local"
    audio_dir: str = "./data/audio"
    upload_dir: str = "./data/uploads"


class ContentConfig(BaseModel):
    max_content_length: int = 50000
    min_content_length: int = 100
    remove_ads: bool = True
    preserve_links: bool = False


class Config(BaseModel):
    api: ApiConfig = Field(default_factory=ApiConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    content: ContentConfig = Field(default_factory=ContentConfig)


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR} patterns with environment variable values."""

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, "")

    return re.sub(r"\$\{(\w+)\}", replacer, value)


def _process_env_vars(data: object) -> object:
    """Recursively substitute env vars in all string values."""
    if isinstance(data, str):
        return _substitute_env_vars(data)
    if isinstance(data, dict):
        return {k: _process_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_process_env_vars(item) for item in data]
    return data


def _load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load and process a YAML config file."""
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    return _process_env_vars(data)  # type: ignore[return-value]


def _build_config(raw: dict[str, Any]) -> Config:
    """Build Config from raw YAML dict, remapping keys as needed."""
    # API config: merge from app, server, and security sections
    api_data = {}
    server = raw.get("server", {})
    app_section = raw.get("app", {})
    security = raw.get("security", {})
    api_data["host"] = server.get("host", "0.0.0.0")
    api_data["port"] = server.get("port", 8000)
    api_data["debug"] = app_section.get("debug", True)
    api_data["enable_docs"] = app_section.get("enable_docs", True)
    api_data["cors_origins"] = security.get("cors_origins", ["*"])

    # Database config: ensure async driver for sqlite
    db_data = raw.get("database", {})
    db_url = db_data.get("url", "sqlite:///./data/newsletter_podcast_dev.db")
    if db_url.startswith("sqlite:///") and "aiosqlite" not in db_url:
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    db_data["url"] = db_url

    # AI services: remap nested structure
    ai = raw.get("ai_services", {})
    llm_data = ai.get("llm", {})
    tts_data = ai.get("tts", {})

    # Remap kokoro -> kokoro_tts to match code expectations
    if "kokoro" in tts_data and "kokoro_tts" not in tts_data:
        tts_data["kokoro_tts"] = tts_data.pop("kokoro")

    # Storage: flatten local sub-config
    storage_raw = raw.get("storage", {})
    storage_data = {
        "type": storage_raw.get("type", "local"),
    }
    local_storage = storage_raw.get("local", {})
    storage_data["audio_dir"] = local_storage.get("audio_dir", "./data/audio")
    storage_data["upload_dir"] = local_storage.get("upload_dir", "./data/uploads")

    return Config(
        api=ApiConfig(**api_data),
        database=DatabaseConfig(**db_data),
        logging=LoggingConfig(**raw.get("logging", {})),
        llm=LLMConfig(**llm_data),
        tts=TTSConfig(**tts_data),
        storage=StorageConfig(**storage_data),
        content=ContentConfig(**raw.get("content", {})),
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Get application configuration (cached)."""
    environment = os.environ.get("ENVIRONMENT", "development")
    config_dir = Path(__file__).parent.parent.parent / "config"
    config_path = config_dir / f"{environment}.yaml"
    raw = _load_yaml_config(config_path)
    return _build_config(raw)


# Alias used in some test helpers
get_settings = get_config
