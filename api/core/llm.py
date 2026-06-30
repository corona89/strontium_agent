import json
import logging
from typing import TYPE_CHECKING, AsyncIterator

import httpx

from core import crypto
from core.config import settings

if TYPE_CHECKING:
    from database.models import LLMProvider

logger = logging.getLogger(__name__)

_PROVIDERS_DEFAULT_BASE = {
    "ollama_cloud": "https://ollama.com",
    "opencode_zen": "https://opencode.ai/zen",
    # ABCLab base는 환경변수로 조정 가능 (코드가 /v1/... 경로를 붙이므로 /v1 제외)
    "abclab": settings.ABCLAB_BASE_URL,
}


def resolve_api_key(provider: "LLMProvider") -> str | None:
    """제공자의 암호화된 API 키를 복호화해 평문으로 반환한다.
    평문 키는 백엔드 메모리에서만 사용하고 로그/응답에 노출하지 않는다(NFR-S11)."""
    return crypto.decrypt(provider.api_key_encrypted)


async def list_enabled_models(
    provider_type: str, base_url: str | None, api_key: str
) -> set[str] | None:
    """제공자 API에서 현재 키로 사용 가능한 모델 ID 집합을 반환한다.
    조회 실패 시 None(검증 건너뜀). Ollama Cloud: GET /api/tags, OpenAI 호환(opencode_zen/abclab): GET /v1/models."""
    if not api_key:
        return None
    if provider_type == "ollama_cloud":
        url = f"{base_url or _PROVIDERS_DEFAULT_BASE['ollama_cloud']}/api/tags"
        headers = {"Authorization": f"Bearer {api_key}"}
        models_key = "models"
        name_key = "name"
    elif provider_type in ("opencode_zen", "abclab"):
        url = f"{base_url or _PROVIDERS_DEFAULT_BASE[provider_type]}/v1/models"
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "strontium-agent/1.0"}
        models_key = "data"
        name_key = "id"
    else:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None
            data = resp.json()
        items = data.get(models_key) or []
        return {str(m.get(name_key)) for m in items if m.get(name_key)}
    except (httpx.HTTPError, ValueError):
        return None


class _EndpointNotSupported(RuntimeError):
    """프로바이더가 해당 엔드포인트(예: /v1/responses)를 지원하지 않아
    다른 엔드포인트로의 폴백이 필요함. 상태코드 404/405/415에서 발생한다."""
    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        super().__init__(f"endpoint not supported ({status_code}): {detail}")


async def _raise_http_error(resp: httpx.Response, provider_label: str) -> None:
    """비-2xx 응답에서 본문을 읽어 명확한 RuntimeError로 변환한다.
    raise_for_status() 대신 사용 — generic httpx 에러가 상위에서 가려지는 것을 방지."""
    if resp.is_success:
        return
    body = ""
    try:
        raw = await resp.aread()
        body = raw.decode("utf-8", errors="replace")
    except Exception:
        pass
    # JSON 에러 본문에서 message 추출 시도
    detail = body
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict) and err.get("message"):
                detail = str(err["message"])
            elif isinstance(data.get("message"), str):
                detail = data["message"]
    except (json.JSONDecodeError, ValueError):
        pass
    detail = (detail or "").strip()[:300]
    if resp.status_code == 401:
        lowered = detail.lower()
        if "disabled" in lowered or "unauthorized" in lowered or "invalid" in lowered:
            raise RuntimeError(
                f"{provider_label}: 해당 모델이 이 API 키에서 사용 불가능합니다(401). "
                f"API 키가 만료되었거나, 모델 식별자가 잘못되었거나, 이 키에서 해당 모델이 비활성화되었을 수 있습니다. "
                f"모델 관리에서 사용 가능한 모델 식별자를 확인하세요. ({detail})"
            )
        raise RuntimeError(
            f"{provider_label}: 인증 실패(401) — API 키가 유효하지 않거나 만료되었습니다. ({detail})"
        )
    if resp.status_code == 403:
        raise RuntimeError(
            f"{provider_label}: 접근 거부(403) — 결제/구독 필요하거나 권한이 없습니다. ({detail})"
        )
    if resp.status_code == 404:
        raise RuntimeError(
            f"{provider_label}: 엔드포인트/모델을 찾을 수 없습니다(404). base_url과 모델 식별자를 확인하세요. ({detail})"
        )
    raise RuntimeError(f"{provider_label} API 오류 ({resp.status_code}): {detail}")


async def stream_chat(
    provider_type: str,
    base_url: str | None,
    model: str,
    messages: list[dict],
    api_key: str,
) -> AsyncIterator[str]:
    """LLM과 스트리밍 채팅. 텍스트 델타를 yield한다. api_key는 호출자가 resolve_api_key로 복호화해 전달."""
    if not api_key:
        raise RuntimeError(f"{provider_type} API 키가 제공자에 설정되어 있지 않습니다")

    if provider_type == "ollama_cloud":
        async for chunk in _stream_ollama(base_url, model, messages, api_key):
            yield chunk
    elif provider_type == "opencode_zen":
        async for chunk in _stream_openai_compat(
            provider_type, base_url, model, messages, api_key, "OpenCode Zen"
        ):
            yield chunk
    elif provider_type == "abclab":
        async for chunk in _stream_openai_compat(
            provider_type, base_url, model, messages, api_key, "ABCLab"
        ):
            yield chunk
    else:
        raise RuntimeError(f"지원하지 않는 제공자 타입: {provider_type}")


async def chat_complete(
    provider_type: str,
    base_url: str | None,
    model: str,
    messages: list[dict],
    api_key: str,
) -> str:
    """스트리밍을 모아 전체 응답 문자열을 반환한다 (플랜 생성 등)."""
    chunks: list[str] = []
    async for chunk in stream_chat(provider_type, base_url, model, messages, api_key):
        chunks.append(chunk)
    return "".join(chunks)


def _build_image_messages(
    provider_type: str, model: str, prompt: str, image_b64: str, mime: str
) -> list[dict]:
    """비전 요청용 messages를 제공자/모델 패밀리에 맞게 구성한다.

    stream_chat의 기존 라우팅과 SSE 파서를 그대로 재사용한다.
    미지원 모델이면 제공자 API가 오류를 반환하고 _raise_http_error가 RuntimeError로 변환한다.
    """
    data_url = f"data:{mime};base64,{image_b64}"
    model_lower = model.lower()
    if provider_type == "ollama_cloud":
        # Ollama: message.images 필드에 base64 원문
        return [{"role": "user", "content": prompt, "images": [image_b64]}]
    if model_lower.startswith("gpt"):
        # OpenAI Responses API: input_text / input_image 블록
        return [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": {"url": data_url}},
                ],
            }
        ]
    if model_lower.startswith("claude"):
        # Anthropic Messages API: text / image(base64 source) 블록
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": image_b64},
                    },
                ],
            }
        ]
    # 표준 OpenAI 호환: text / image_url(data URL) 블록
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]


async def describe_image(
    provider_type: str,
    base_url: str | None,
    model: str,
    prompt: str,
    image_bytes: bytes,
    mime: str,
    api_key: str,
) -> str:
    """비전 모델로 이미지를 묘사/분석해 텍스트를 반환한다.
    비전 미지원 모델이면 제공자 API 오류가 RuntimeError로 전파된다(라우터에서 400 처리)."""
    import base64

    b64 = base64.b64encode(image_bytes).decode("ascii")
    messages = _build_image_messages(provider_type, model, prompt, b64, mime)
    chunks: list[str] = []
    async for delta in stream_chat(provider_type, base_url, model, messages, api_key):
        chunks.append(delta)
    return "".join(chunks)


async def _stream_ollama(
    base_url: str | None, model: str, messages: list[dict], api_key: str
) -> AsyncIterator[str]:
    url = f"{base_url or _PROVIDERS_DEFAULT_BASE['ollama_cloud']}/api/chat"
    payload = {"model": model, "messages": messages, "stream": True}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST", url, json=payload, headers={"Authorization": f"Bearer {api_key}"}
        ) as resp:
            await _raise_http_error(resp, "Ollama Cloud")
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = (data.get("message") or {}).get("content")
                if delta:
                    yield delta


async def _stream_openai_compat(
    provider_type: str,
    base_url: str | None,
    model: str,
    messages: list[dict],
    api_key: str,
    label: str,
) -> AsyncIterator[str]:
    """OpenAI 호환 제공자(opencode_zen, abclab) 공용 스트리머.
    모델 패밀리별 엔드포인트 라우팅(대소문자 무시 매칭).
    GPT 계열: /v1/responses (OpenAI Responses API)
    Claude 계열: /v1/messages (Anthropic Messages API)
    그 외(GLM/Qwen/DeepSeek/Kimi/MiniMax/Grok 등): /v1/chat/completions (표준 OpenAI 호환)"""
    base = base_url or _PROVIDERS_DEFAULT_BASE[provider_type]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "strontium-agent/1.0 ai-sdk/provider-utils",
    }
    model_lower = model.lower()

    if model_lower.startswith("gpt"):
        url_r = f"{base}/v1/responses"
        payload_r: dict = {"model": model, "input": messages, "stream": True}
        try:
            async for chunk in _stream_oai_responses(url_r, payload_r, headers, label):
                yield chunk
        except _EndpointNotSupported as e:
            logger.debug(
                "%s: /v1/responses 미지원(status=%s) — /v1/chat/completions 폴백",
                label, e.status_code,
            )
            url_c = f"{base}/v1/chat/completions"
            payload_c = {"model": model, "messages": messages, "stream": True}
            async for chunk in _stream_oai_chat(url_c, payload_c, headers, label):
                yield chunk
    elif model_lower.startswith("claude"):
        url = f"{base}/v1/messages"
        system_text = None
        conv: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            else:
                conv.append(m)
        payload = {"model": model, "messages": conv, "max_tokens": 4096, "stream": True}
        if system_text:
            payload["system"] = system_text
        async for chunk in _stream_oai_messages(url, payload, headers, label):
            yield chunk
    else:
        url = f"{base}/v1/chat/completions"
        payload = {"model": model, "messages": messages, "stream": True}
        async for chunk in _stream_oai_chat(url, payload, headers, label):
            yield chunk


async def _stream_oai_chat(
    url: str, payload: dict, headers: dict, label: str
) -> AsyncIterator[str]:
    """표준 OpenAI 호환 /v1/chat/completions SSE 스트리밍."""
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            await _raise_http_error(resp, label)
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]" or not data_str:
                    continue
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield content


async def _stream_oai_responses(
    url: str, payload: dict, headers: dict, label: str
) -> AsyncIterator[str]:
    """OpenAI Responses API /v1/responses SSE 스트리밍 (GPT 계열).

    response.output_text.delta 이벤트만 처리한다. snapshot 계열 이벤트
    (.done/.completed 등)는 지금까지 누적된 전체 텍스트를 담고 있어 이를
    yield하면 스트림 버퍼에 전체 응답이 중복 삽입되므로 무시한다.
    404/405/415 수신 시 _EndpointNotSupported를 raise해 상위에서 폴백하게 한다."""
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code in (404, 405, 415):
                body = ""
                try:
                    body = (await resp.aread()).decode("utf-8", errors="replace")[:200]
                except Exception:
                    pass
                raise _EndpointNotSupported(resp.status_code, body)
            await _raise_http_error(resp, label)
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]" or not data_str:
                    continue
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                etype = data.get("type", "")
                if etype == "response.output_text.delta":
                    delta = data.get("delta")
                    if isinstance(delta, str) and delta:
                        yield delta
                elif etype and etype not in (
                    "response.created", "response.in_progress",
                ):
                    logger.debug(
                        "%s /v1/responses: delta 외 이벤트 무시 type=%s keys=%s",
                        label, etype, sorted(data.keys()),
                    )


async def _stream_oai_messages(
    url: str, payload: dict, headers: dict, label: str
) -> AsyncIterator[str]:
    """Anthropic Messages API /v1/messages SSE 스트리밍 (Claude 계열)."""
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            await _raise_http_error(resp, label)
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if not data_str:
                    continue
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                # content_block_delta 이벤트의 delta.text
                if data.get("type") == "content_block_delta":
                    delta = data.get("delta") or {}
                    text = delta.get("text")
                    if isinstance(text, str) and text:
                        yield text
