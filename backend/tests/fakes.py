"""테스트용 가짜 LLM. 실제 Claude API를 호출하지 않는다."""

from collections.abc import Callable
from typing import Any


class FakeLLM:
    def __init__(self) -> None:
        self.responses: dict[type, Any] = {}
        self.calls: list[dict] = []
        self.error: Exception | None = None

    def set(self, output_type: type, value: Any | Callable[[str, str], Any]) -> None:
        """value는 모델 인스턴스, 또는 (system, user)를 받아 인스턴스를 돌려주는 함수"""
        self.responses[output_type] = value

    def parse(self, *, system: str, user: str, output_type: type, max_tokens: int):
        self.calls.append(
            {"system": system, "user": user, "output_type": output_type, "max_tokens": max_tokens}
        )
        if self.error:
            raise self.error
        value = self.responses[output_type]
        return value(system, user) if callable(value) else value
