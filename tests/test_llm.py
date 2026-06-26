"""LLM re-rank layer: provider resolution, Ollama dispatch, graceful fallback.

No real Ollama server or API key is needed — the HTTP call is mocked.
"""
from __future__ import annotations

import json
import urllib.error

import pytest

import app.llm as llm
from app.config import Settings


# --- provider resolution -----------------------------------------------------
def test_default_provider_is_ollama(monkeypatch):
    # With nothing set, the app defaults to the local Ollama re-rank layer.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("USE_LLM_RERANK", raising=False)
    from app.config import _provider

    assert _provider() == "ollama"


def test_provider_env_selects_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    from app.config import _provider

    assert _provider() == "ollama"


def test_provider_env_selects_vllm(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    from app.config import _provider

    assert _provider() == "vllm"


def test_external_provider_is_rejected(monkeypatch):
    # No external ML/chatbot API allowed: an unknown/cloud provider falls back
    # to the local default rather than being honored.
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    from app.config import _provider

    assert _provider() == "ollama"


def test_only_local_providers_are_valid():
    from app.config import _VALID_PROVIDERS

    assert _VALID_PROVIDERS == {"none", "ollama", "vllm"}


def test_llm_enabled_per_provider():
    assert Settings(llm_provider="none").llm_enabled is False
    assert Settings(llm_provider="ollama").llm_enabled is True
    assert Settings(llm_provider="vllm").llm_enabled is True


# --- response parsing --------------------------------------------------------
def test_parse_plain_json():
    assert llm._parse('{"order": [2, 1], "rationale": "x"}')["order"] == [2, 1]


def test_parse_fenced_json():
    assert llm._parse('```json\n{"order": [1]}\n```')["order"] == [1]


@pytest.mark.parametrize("bad", ["", "not json", "{}", '{"order": "nope"}', "[1,2,3]"])
def test_parse_rejects_invalid(bad):
    assert llm._parse(bad) is None


# --- Ollama dispatch (mocked HTTP) -------------------------------------------
class _FakeResp:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._data


def test_ollama_rerank_success(monkeypatch):
    monkeypatch.setattr(llm, "settings", Settings(llm_provider="ollama"))
    reply = {"message": {"content": json.dumps({"order": [2, 1], "rationale": "closest"})}}
    monkeypatch.setattr(
        llm.urllib.request, "urlopen", lambda req, timeout=None: _FakeResp(reply)
    )
    out = llm.llm_rerank("Toshkent", [{"mashina_id": 1}, {"mashina_id": 2}])
    assert out is not None
    assert out["order"] == [2, 1]
    assert out["rationale"] == "closest"


def test_ollama_server_down_returns_none(monkeypatch):
    monkeypatch.setattr(llm, "settings", Settings(llm_provider="ollama"))

    def boom(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    # Must degrade gracefully, not raise.
    assert llm.llm_rerank("Toshkent", [{"mashina_id": 1}]) is None


def test_disabled_provider_skips_call(monkeypatch):
    monkeypatch.setattr(llm, "settings", Settings(llm_provider="none"))

    def fail(*a, **k):  # must never be reached
        raise AssertionError("LLM called while disabled")

    monkeypatch.setattr(llm.urllib.request, "urlopen", fail)
    assert llm.llm_rerank("Toshkent", [{"mashina_id": 1}]) is None


# --- vLLM dispatch (OpenAI-compatible, mocked HTTP) --------------------------
def test_vllm_rerank_success(monkeypatch):
    monkeypatch.setattr(llm, "settings", Settings(llm_provider="vllm"))
    content = json.dumps({"order": [3, 1], "rationale": "nearest"})
    reply = {"choices": [{"message": {"content": content}}]}
    monkeypatch.setattr(
        llm.urllib.request, "urlopen", lambda req, timeout=None: _FakeResp(reply)
    )
    out = llm.llm_rerank("Samarqand", [{"mashina_id": 1}, {"mashina_id": 3}])
    assert out is not None and out["order"] == [3, 1]


def test_vllm_server_down_returns_none(monkeypatch):
    monkeypatch.setattr(llm, "settings", Settings(llm_provider="vllm"))

    def boom(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    assert llm.llm_rerank("Samarqand", [{"mashina_id": 1}]) is None


def test_vllm_malformed_response_returns_none(monkeypatch):
    monkeypatch.setattr(llm, "settings", Settings(llm_provider="vllm"))
    # Missing the expected choices[0].message.content shape.
    monkeypatch.setattr(
        llm.urllib.request, "urlopen", lambda req, timeout=None: _FakeResp({"oops": 1})
    )
    assert llm.llm_rerank("Samarqand", [{"mashina_id": 1}]) is None
