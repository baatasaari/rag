"""
Circuit breaker for the LBG RAG storage layer.

Implements the standard CLOSED → OPEN → HALF_OPEN → CLOSED state machine.

State transitions:
  CLOSED   → OPEN        when consecutive failures >= failure_threshold
  OPEN     → HALF_OPEN   after open_duration_seconds have elapsed
  HALF_OPEN→ CLOSED      when consecutive successes >= success_threshold_to_close
  HALF_OPEN→ OPEN        on any failure

Usage::

    breaker = CircuitBreaker("alloydb_pgvector", config.resilience.circuit_breaker)
    result = await breaker.call(my_async_fn(arg1, arg2))

    # Or store per-component breakers in a registry:
    breaker = get_breaker("embedding.vertex_ai", config)
"""

from __future__ import annotations

import asyncio
import functools
import time
from enum import Enum
from typing import Any, Awaitable, TypeVar

from rag.core.exceptions import CircuitBreakerOpenError
from rag.core.schemas import CircuitBreakerConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import record_span

log = get_logger(__name__)

T = TypeVar("T")

# Module-level registry so callers can share breakers by name.
_breakers: dict[str, CircuitBreaker] = {}


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Async circuit breaker guarding a single downstream component.

    All state mutations are protected by an asyncio.Lock so concurrent callers
    see a consistent view of the state machine.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig) -> None:
        self._name = name
        self._config = config
        self._state: CircuitState = CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._consecutive_successes: int = 0
        self._opened_at: float = 0.0
        self._lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, coro: Awaitable[T]) -> T:
        """Execute *coro*, applying circuit-breaker logic.

        Raises:
            CircuitBreakerOpenError: If the breaker is OPEN and the probe
                window has not yet elapsed.
        """
        if not self._config.enabled:
            return await coro

        await self._check_and_maybe_transition()

        try:
            result = await coro
            await self._record_success()
            return result  # type: ignore[return-value]
        except CircuitBreakerOpenError:
            raise  # never count breaker errors as failures
        except Exception:
            await self._record_failure()
            raise

    # ------------------------------------------------------------------
    # State checks and transitions (all under lock)
    # ------------------------------------------------------------------

    async def _check_and_maybe_transition(self) -> None:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self._config.open_duration_seconds:
                    self._transition_to(CircuitState.HALF_OPEN)
                else:
                    retry_after = self._config.open_duration_seconds - elapsed
                    raise CircuitBreakerOpenError(self._name, retry_after_seconds=retry_after)

    async def _record_success(self) -> None:
        async with self._lock:
            self._consecutive_failures = 0
            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self._config.success_threshold_to_close:
                    self._transition_to(CircuitState.CLOSED)
            # CLOSED state: success is the normal case, nothing to do.

    async def _record_failure(self) -> None:
        async with self._lock:
            self._consecutive_failures += 1
            self._consecutive_successes = 0
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif (
                self._state == CircuitState.CLOSED
                and self._consecutive_failures >= self._config.failure_threshold
            ):
                self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state
        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
            self._consecutive_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._consecutive_failures = 0
            self._consecutive_successes = 0
        log.info(
            "circuit_breaker.transition",
            component=self._name,
            old_state=old_state.value,
            new_state=new_state.value,
            consecutive_failures=self._consecutive_failures,
        )
        self._update_metrics(new_state)

    def _update_metrics(self, state: CircuitState) -> None:
        try:
            from rag.observability.metrics import get_metrics

            m = get_metrics()
            state_value = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}[state.value]
            m.circuit_breaker_state.add(state_value, {"component": self._name})
            if state == CircuitState.OPEN:
                m.circuit_breaker_trips_total.add(1, {"component": self._name})
        except RuntimeError:
            pass  # metrics not configured


# ---------------------------------------------------------------------------
# Module-level breaker registry
# ---------------------------------------------------------------------------


def get_breaker(name: str, config: CircuitBreakerConfig) -> CircuitBreaker:
    """Return a shared CircuitBreaker for *name*, creating it if needed."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name, config)
    return _breakers[name]


def reset_breakers() -> None:
    """Clear all registered circuit breakers.  FOR TESTING ONLY."""
    _breakers.clear()
