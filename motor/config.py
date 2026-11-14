"""Carga la configuración desde el archivo .env de la raíz del proyecto."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROYECTO / ".env")


def _texto(nombre, defecto=""):
    return os.getenv(nombre, defecto).strip()


def _lista(nombre, defecto=""):
    return [x.strip() for x in _texto(nombre, defecto).split(",") if x.strip()]


@dataclass
class Config:
    llm_modelo: str = field(default_factory=lambda: _texto("LLM_MODELO", "anthropic/claude-haiku-5-5"))
    # Sin .env, el respaldo son las respuestas guardadas del laboratorio, para que la demo funcione sin claves.
    llm_modelos_respaldo: list = field(default_factory=lambda: _lista("LLM_MODELOS_RESPALDO", "manual/claude-opus-5-5-sesion"))
    openai_api_key: str = field(default_factory=lambda: _texto("OPENAI_API_KEY"))
    anthropic_api_key: str = field(default_factory=lambda: _texto("ANTHROPIC_API_KEY"))
    openrouter_api_key: str = field(default_factory=lambda: _texto("OPENROUTER_API_KEY"))
    openrouter_base_url: str = field(default_factory=lambda: _texto("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    ollama_base_url: str = field(default_factory=lambda: _texto("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    openai_base_url: str = field(default_factory=lambda: _texto("OPENAI_BASE_URL"))
    llm_temperatura: float = field(default_factory=lambda: float(_texto("LLM_TEMPERATURA", "0")))
    llm_max_tokens: int = field(default_factory=lambda: int(_texto("LLM_MAX_TOKENS", "2000")))
    llm_timeout: float = field(default_factory=lambda: float(_texto("LLM_TIMEOUT_SEGUNDOS", "60")))
    llm_cache: bool = field(default_factory=lambda: _texto("LLM_CACHE", "1") == "1")
    umbral_similitud: float = field(default_factory=lambda: float(_texto("ECO_UMBRAL_SIMILITUD", "0.6")))
    dir_cache: Path = RAIZ_PROYECTO / ".cache" / "llm"


config = Config()
