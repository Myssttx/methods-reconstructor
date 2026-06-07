"""Per-job approximate LLM token accounting.

Provider tokenizers differ, so this deliberately uses a conservative character
estimate. The guardrail is for runaway prevention, not billing reconciliation.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


class TokenBudgetExceededError(RuntimeError):
    pass


@dataclass
class TokenBudget:
    limit: int
    used: int = 0

    def charge(self, text: str) -> None:
        estimated = max(1, (len(text) + 2) // 3)
        if self.used + estimated > self.limit:
            raise TokenBudgetExceededError(
                f"LLM token budget exceeded: estimated {self.used + estimated:,} "
                f"tokens exceeds limit {self.limit:,}"
            )
        self.used += estimated


_current_budget: ContextVar[TokenBudget | None] = ContextVar("llm_token_budget", default=None)


@contextmanager
def token_budget(limit: int) -> Iterator[TokenBudget]:
    budget = TokenBudget(limit=limit)
    token = _current_budget.set(budget)
    try:
        yield budget
    finally:
        _current_budget.reset(token)


def charge_llm_text(text: str) -> None:
    budget = _current_budget.get()
    if budget is not None:
        budget.charge(text)
