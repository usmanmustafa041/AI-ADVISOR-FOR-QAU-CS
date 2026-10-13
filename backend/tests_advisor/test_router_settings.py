import asyncio

import pytest

from advisor.config import Settings
from advisor.db import Database
from advisor.llm.base import GenParams, Message, MidStreamError, ProviderError
from advisor.llm.router import NoProviderAvailable, ProviderRouter
from advisor.runtime_settings import RuntimeSettings
from advisor.security import SecretBox, hash_password, mask_secret, verify_password


@pytest.fixture
def rt(tmp_path):
    s = Settings(data_dir=tmp_path)
    db = Database(s.db_path)
    return RuntimeSettings(db, SecretBox(tmp_path), s), db, s


class Fake:
    def __init__(self, name, script):
        self.name, self.model, self.script, self.calls = name, f"{name}-model", script, 0

    async def stream(self, messages, params):
        self.calls += 1
        for item in self.script:
            if isinstance(item, Exception):
                raise item
            yield item

    async def complete(self, messages, params):
        return "".join([c async for c in self.stream(messages, params)])


def run_router(router, **kw):
    async def go():
        return [x async for x in router.stream([Message("user", "q")], GenParams(), **kw)]

    return asyncio.run(go())


def make_router(rt, providers):
    runtime, _db, s = rt
    router = ProviderRouter(s, runtime)
    router.candidates = lambda: providers  # type: ignore[method-assign]
    return router


def test_secret_is_encrypted_at_rest_masked_and_clearable(rt):
    runtime, db, _ = rt
    runtime.set("gemini.api_key", "AIzaSyDUMMYKEY1234567890", "tester")
    stored = db.one("SELECT value, is_secret FROM settings WHERE key='gemini.api_key'")
    assert stored["is_secret"] == 1 and "DUMMYKEY" not in stored["value"]
    assert runtime.get("gemini.api_key") == "AIzaSyDUMMYKEY1234567890"
    view = {s["key"]: s for s in runtime.public_view()}["gemini.api_key"]
    assert view["configured"] and view["value"] == "" and "DUMMYKEY" not in str(view)
    runtime.set("gemini.api_key", "", "tester")
    assert runtime.get("gemini.api_key") == ""


def test_setting_validation(rt):
    runtime, *_ = rt
    with pytest.raises(ValueError):
        runtime.set("llm.primary", "chatgpt")
    with pytest.raises(ValueError):
        runtime.set("llm.temperature", 3)
    with pytest.raises(ValueError):
        runtime.set("ollama.base_url", "ftp://nope")
    runtime.set("llm.temperature", "0.4")
    assert runtime.get("llm.temperature") == 0.4
    runtime.set("gemini.enabled", "false")
    assert runtime.get("gemini.enabled") is False


def test_env_key_is_used_until_admin_overrides(tmp_path):
    s = Settings(data_dir=tmp_path, gemini_api_key="ENVKEY")
    r = RuntimeSettings(Database(s.db_path), SecretBox(tmp_path), s)
    assert r.get("gemini.api_key") == "ENVKEY"
    r.set("gemini.api_key", "ADMINKEY")
    assert r.get("gemini.api_key") == "ADMINKEY"


def test_router_order_follows_settings(rt):
    runtime, _db, s = rt
    router = ProviderRouter(s, runtime)
    assert [p.name for p in router.candidates()] == ["ollama"]  # no key => local only
    runtime.set("gemini.api_key", "k")
    assert [p.name for p in router.candidates()] == ["gemini", "ollama"]
    runtime.set("llm.primary", "ollama")
    assert [p.name for p in router.candidates()] == ["ollama", "gemini"]
    runtime.set("gemini.enabled", False)
    assert [p.name for p in router.candidates()] == ["ollama"]


def test_failover_to_next_provider_before_first_token(rt):
    bad = Fake("gemini", [ProviderError("gemini", "quota", "429")])
    good = Fake("ollama", ["Hel", "lo"])
    out = run_router(make_router(rt, [bad, good]))
    assert "".join(t for _p, _m, t in out) == "Hello" and out[0][0] == "ollama"


def test_mid_stream_failure_is_surfaced_not_hidden(rt):
    flaky = Fake("gemini", ["part", MidStreamError("gemini", "timeout", "died")])
    with pytest.raises(MidStreamError):
        run_router(make_router(rt, [flaky, Fake("ollama", ["x"])]))


def test_all_providers_failing_raises_with_reasons(rt):
    a = Fake("gemini", [ProviderError("gemini", "auth", "bad key", retryable=False)])
    b = Fake("ollama", [ProviderError("ollama", "unavailable", "down")])
    with pytest.raises(NoProviderAvailable) as exc:
        run_router(make_router(rt, [a, b]))
    assert "bad key" in str(exc.value) and "down" in str(exc.value)


def test_circuit_breaker_skips_a_failing_provider(rt):
    bad = Fake("gemini", [ProviderError("gemini", "auth", "bad key", retryable=False)])
    good = Fake("ollama", ["ok"])
    router = make_router(rt, [bad, good])
    run_router(router)
    run_router(router)
    assert bad.calls == 1 and good.calls == 2  # second request skipped the paused provider


def test_skip_set_excludes_providers(rt):
    a, b = Fake("gemini", ["A"]), Fake("ollama", ["B"])
    out = run_router(make_router(rt, [a, b]), skip={"gemini"})
    assert out[0][2] == "B" and a.calls == 0


def test_password_hashing():
    h = hash_password("correct horse battery")
    assert verify_password("correct horse battery", h) and not verify_password("wrong", h)
    assert "correct" not in h
    assert mask_secret("AIzaSyABCDEFGHIJKLM") == "AIza…JKLM"
