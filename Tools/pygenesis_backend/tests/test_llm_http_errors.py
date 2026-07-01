from providers.llm_http_errors import LLMProviderHttpError, user_notice_for_provider_error


def test_user_notice_429_from_exception_type():
    ex = LLMProviderHttpError("upstream", status_code=429)
    n = user_notice_for_provider_error(ex)
    assert n is not None
    assert "429" in n
    assert "cuota" in n.lower() or "ritmo" in n.lower()


def test_user_notice_429_from_message_string():
    ex = RuntimeError('LLM API HTTP 429: {"error":}')
    n = user_notice_for_provider_error(ex)
    assert n is not None
    assert "429" in n


def test_user_notice_unknown_returns_none():
    assert user_notice_for_provider_error(RuntimeError("timeout")) is None
