"""Claude API 호출 래퍼.

- structured outputs(messages.parse + Pydantic)로 JSON 형식을 강제한다.
- 동기 클라이언트를 쓰므로 이걸 부르는 FastAPI 엔드포인트는 `def`로 만든다
  (FastAPI가 스레드풀에서 돌려서 이벤트 루프를 막지 않음).
- 테스트에서는 같은 인터페이스의 가짜 클라이언트로 바꿔 끼운다 (CI에서 실제 API 호출 안 함).
"""

from typing import Protocol, TypeVar

import anthropic
import pydantic

T = TypeVar("T", bound=pydantic.BaseModel)


class LLMError(RuntimeError):
    """LLM 호출 실패 또는 응답이 스키마에 맞지 않음."""


class LLMClient(Protocol):
    def parse(self, *, system: str, user: str, output_type: type[T], max_tokens: int) -> T: ...


class AnthropicLLM:
    def __init__(self, api_key: str, model: str, timeout: float = 30.0):
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def parse(self, *, system: str, user: str, output_type: type[T], max_tokens: int) -> T:
        try:
            resp = self._client.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=output_type,
            )
        except anthropic.APIError as e:
            raise LLMError(f"Claude API 호출 실패: {e}") from e
        except pydantic.ValidationError as e:
            raise LLMError(f"응답이 스키마와 맞지 않음: {e}") from e

        # 토큰 한도에 걸려 잘렸거나 거절된 응답은 스키마를 보장하지 않는다.
        if resp.stop_reason in ("max_tokens", "refusal"):
            raise LLMError(f"응답이 완전하지 않음 (stop_reason={resp.stop_reason})")
        if resp.parsed_output is None:
            raise LLMError("응답에서 JSON을 읽지 못함")
        return resp.parsed_output
