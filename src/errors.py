"""统一错误码定义。

设计目标：让调用方（HTTP / CLI）能根据稳定的 `code` 字段判断失败类型，
而不依赖易变的错误文案。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCode:
    code: str
    http_status: int
    message: str


# 输入相关
EMPTY_INPUT = ErrorCode("E1001", 400, "Empty message: 'message' field is required and must be non-empty.")
INVALID_PAYLOAD = ErrorCode("E1002", 400, "Invalid request payload.")

# 知识库 / 检索
KNOWLEDGE_LOAD_FAILED = ErrorCode("E2001", 500, "Failed to load knowledge base.")

# LLM 相关
LLM_INVALID_JSON = ErrorCode("E3001", 200, "LLM returned invalid JSON; recovered via repair/fallback.")
LLM_CALL_FAILED = ErrorCode("E3002", 200, "LLM call failed; degraded to rule-based answer.")

# 兜底
INTERNAL_ERROR = ErrorCode("E5000", 500, "Internal server error.")


class AgentError(Exception):
    """业务异常，携带稳定错误码。"""

    def __init__(self, error: ErrorCode, detail: str | None = None):
        self.error = error
        self.detail = detail or error.message
        super().__init__(self.detail)

    def to_dict(self) -> dict:
        return {"error_code": self.error.code, "error": self.detail}
