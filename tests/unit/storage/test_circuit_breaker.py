"""
Tests for rag.storage.circuit_breaker — state machine, transitions, decorator.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from rag.core.exceptions import CircuitBreakerOpenError
from rag.storage.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    get_breaker,
    reset_breakers,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_breakers():
    reset_breakers()
    yield
    reset_breakers()


def _make_config(
    *,
    enabled: bool = True,
    failure_threshold: int = 3,
    window_seconds: int = 30,
    open_duration_seconds: int = 60,
    success_threshold_to_close: int = 2,
) -> MagicMock:
    cfg = MagicMock()
    cfg.enabled = enabled
    cfg.failure_threshold = failure_threshold
    cfg.window_seconds = window_seconds
    cfg.open_duration_seconds = open_duration_seconds
    cfg.success_threshold_to_close = success_threshold_to_close
    return cfg


async def _succeed() -> str:
    return "ok"


async def _fail() -> None:
    raise RuntimeError("downstream error")


# ── Initial state ─────────────────────────────────────────────────────────────


class TestInitialState:
    def test_starts_closed(self):
        breaker = CircuitBreaker("test", _make_config())
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_passes_calls_through_when_closed(self):
        breaker = CircuitBreaker("test", _make_config())
        result = await breaker.call(_succeed())
        assert result == "ok"


# ── CLOSED → OPEN transition ──────────────────────────────────────────────────


class TestClosedToOpen:
    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        breaker = CircuitBreaker("test", _make_config(failure_threshold=3))
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(_fail())
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_does_not_open_before_threshold(self):
        breaker = CircuitBreaker("test", _make_config(failure_threshold=3))
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(_fail())
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        breaker = CircuitBreaker("test", _make_config(failure_threshold=3))
        with pytest.raises(RuntimeError):
            await breaker.call(_fail())
        with pytest.raises(RuntimeError):
            await breaker.call(_fail())
        await breaker.call(_succeed())  # resets count
        with pytest.raises(RuntimeError):
            await breaker.call(_fail())
        # Only 1 failure since reset — still CLOSED
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_open_raises_circuit_breaker_open_error(self):
        breaker = CircuitBreaker("test", _make_config(failure_threshold=2))
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(_fail())
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(_succeed())

    @pytest.mark.asyncio
    async def test_open_error_includes_component_name(self):
        breaker = CircuitBreaker("my_component", _make_config(failure_threshold=1))
        with pytest.raises(RuntimeError):
            await breaker.call(_fail())
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await breaker.call(_succeed())
        assert "my_component" in str(exc_info.value)


# ── OPEN → HALF_OPEN transition ───────────────────────────────────────────────


class TestOpenToHalfOpen:
    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_duration(self):
        breaker = CircuitBreaker(
            "test", _make_config(failure_threshold=1, open_duration_seconds=60)
        )
        with pytest.raises(RuntimeError):
            await breaker.call(_fail())
        assert breaker.state == CircuitState.OPEN

        # Simulate time passing beyond open_duration_seconds
        with patch("rag.storage.circuit_breaker.time.monotonic", return_value=9999.0):
            breaker._opened_at = 0.0  # force elapsed > 60s
            result = await breaker.call(_succeed())
        assert result == "ok"
        assert breaker.state in (CircuitState.HALF_OPEN, CircuitState.CLOSED)

    @pytest.mark.asyncio
    async def test_retry_after_reported_when_still_open(self):
        breaker = CircuitBreaker(
            "test", _make_config(failure_threshold=1, open_duration_seconds=60)
        )
        with pytest.raises(RuntimeError):
            await breaker.call(_fail())
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await breaker.call(_succeed())
        # retry_after_seconds should be present and positive
        err = exc_info.value
        assert err.context.get("retry_after_seconds", 0) > 0


# ── HALF_OPEN → CLOSED transition ────────────────────────────────────────────


class TestHalfOpenToClosed:
    @pytest.mark.asyncio
    async def test_closes_after_success_threshold(self):
        breaker = CircuitBreaker(
            "test",
            _make_config(
                failure_threshold=1,
                open_duration_seconds=0,
                success_threshold_to_close=2,
            ),
        )
        # Open the breaker
        with pytest.raises(RuntimeError):
            await breaker.call(_fail())

        # Force into HALF_OPEN
        breaker._state = CircuitState.HALF_OPEN
        breaker._consecutive_successes = 0

        await breaker.call(_succeed())
        assert breaker.state == CircuitState.HALF_OPEN  # 1 success, need 2
        await breaker.call(_succeed())
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self):
        breaker = CircuitBreaker("test", _make_config(failure_threshold=5))
        breaker._state = CircuitState.HALF_OPEN
        with pytest.raises(RuntimeError):
            await breaker.call(_fail())
        assert breaker.state == CircuitState.OPEN


# ── Disabled breaker ──────────────────────────────────────────────────────────


class TestDisabledBreaker:
    @pytest.mark.asyncio
    async def test_disabled_passes_all_calls(self):
        breaker = CircuitBreaker("test", _make_config(enabled=False))
        for _ in range(10):
            with pytest.raises(RuntimeError):
                await breaker.call(_fail())
        # Still no OPEN transition when disabled
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_disabled_returns_result(self):
        breaker = CircuitBreaker("test", _make_config(enabled=False))
        assert await breaker.call(_succeed()) == "ok"


# ── get_breaker registry ──────────────────────────────────────────────────────


class TestGetBreaker:
    def test_returns_same_instance_for_same_name(self):
        cfg = _make_config()
        b1 = get_breaker("svc_a", cfg)
        b2 = get_breaker("svc_a", cfg)
        assert b1 is b2

    def test_different_names_different_instances(self):
        cfg = _make_config()
        b1 = get_breaker("svc_a", cfg)
        b2 = get_breaker("svc_b", cfg)
        assert b1 is not b2

    def test_reset_clears_registry(self):
        cfg = _make_config()
        b1 = get_breaker("svc_a", cfg)
        reset_breakers()
        b2 = get_breaker("svc_a", cfg)
        assert b1 is not b2


# ── CircuitBreakerOpenError invariants ────────────────────────────────────────


class TestCircuitBreakerOpenError:
    def test_error_is_json_serialisable(self):
        import json

        err = CircuitBreakerOpenError("my_svc", retry_after_seconds=42.0)
        json.dumps(err.to_dict())

    def test_error_component_is_resilience(self):
        err = CircuitBreakerOpenError("svc")
        assert err.component == "resilience"
