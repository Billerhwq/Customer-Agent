"""集中配置：从环境变量 / .env 读取。"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()  # 若存在 .env 则加载；不存在也不报错
except Exception:  # pragma: no cover - dotenv 是可选依赖
    pass


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    llm_mode: str = os.getenv("LLM_MODE", "mock").strip().lower()

    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "30"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "2"))

    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "4"))
    retrieval_min_score: float = float(os.getenv("RETRIEVAL_MIN_SCORE", "0.34"))

    knowledge_path: str = os.getenv("KNOWLEDGE_PATH", "knowledge/company_knowledge.json")
    log_path: str = os.getenv("LOG_PATH", "logs/traces.jsonl")
    db_path: str = os.getenv("DB_PATH", "data/app.db")

    def use_real_llm(self) -> bool:
        return self.llm_mode == "deepseek" and bool(self.deepseek_api_key)


def get_settings() -> Settings:
    """每次读取最新环境（便于测试时覆盖）。"""
    return Settings()
