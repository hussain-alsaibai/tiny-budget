"""
tiny-budget: LLM cost tracking for multi-model AI agents.

Records per-call cost across providers/models/operations and persists to JSON.
Zero dependencies — stdlib only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path.home() / ".tiny-budget.json"


@dataclass
class CallRecord:
    """A single LLM call's tracked metrics."""
    timestamp: str
    provider: str
    model: str
    operation: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float


@dataclass
class CostBudget:
    """
    LLM cost tracker.

    Persists every tracked call to a JSON file. Loads on init; saves after
    each track() call. Safe to use across processes (single-writer assumed).
    """
    path: str | os.PathLike[str] = field(default=DEFAULT_PATH)
    records: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self._load()

    # ---------- persistence ----------

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("records"), list):
                    self.records = data["records"]
            except (json.JSONDecodeError, OSError):
                # corrupt file — start fresh, do not crash caller
                self.records = []
        else:
            self.records = []

    def _save(self) -> None:
        payload = {"records": self.records}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ---------- core API ----------

    def track(
        self,
        provider: str,
        model: str,
        operation: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
    ) -> dict[str, Any]:
        """Record a single LLM call. Returns the recorded dict."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": str(provider),
            "model": str(model),
            "operation": str(operation),
            "tokens_in": int(tokens_in),
            "tokens_out": int(tokens_out),
            "latency_ms": float(latency_ms),
            "cost_usd": float(cost_usd),
        }
        self.records.append(record)
        self._save()
        return record

    def total_cost(self) -> float:
        """Total USD spent across all tracked calls."""
        return round(sum(float(r.get("cost_usd", 0.0)) for r in self.records), 6)

    def total_tokens(self) -> dict[str, int]:
        """Total tokens {in, out} across all tracked calls."""
        return {
            "in": sum(int(r.get("tokens_in", 0)) for r in self.records),
            "out": sum(int(r.get("tokens_out", 0)) for r in self.records),
        }

    def get_by_model(self) -> dict[str, float]:
        """Cost breakdown keyed by model."""
        return self._aggregate(lambda r: r.get("model", ""))

    def get_by_operation(self) -> dict[str, float]:
        """Cost breakdown keyed by operation."""
        return self._aggregate(lambda r: r.get("operation", ""))

    def get_by_provider(self) -> dict[str, float]:
        """Cost breakdown keyed by provider."""
        return self._aggregate(lambda r: r.get("provider", ""))

    def get_summary(self) -> dict[str, Any]:
        """Full stats dict: totals + breakdowns + call count."""
        return {
            "calls": len(self.records),
            "total_cost_usd": self.total_cost(),
            "total_tokens": self.total_tokens(),
            "by_provider": self.get_by_provider(),
            "by_model": self.get_by_model(),
            "by_operation": self.get_by_operation(),
        }

    def reset(self) -> None:
        """Clear all data and persist."""
        self.records = []
        self._save()

    # ---------- internal ----------

    def _aggregate(self, key_fn) -> dict[str, float]:
        out: dict[str, float] = {}
        for r in self.records:
            key = key_fn(r)
            if not key:
                continue
            out[key] = round(out.get(key, 0.0) + float(r.get("cost_usd", 0.0)), 6)
        return out


def main() -> None:  # pragma: no cover
    """Tiny CLI: prints summary of the budget file at DEFAULT_PATH."""
    cb = CostBudget()
    summary = cb.get_summary()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()