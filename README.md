# tiny-budget

[![CI](https://github.com/hussain-alsaibai/tiny-budget/actions/workflows/ci.yml/badge.svg)](https://github.com/hussain-alsaibai/tiny-budget/actions)
[![Install from GitHub](https://img.shields.io/badge/install-git%2Bhttps-blue)](https://github.com/hussain-alsaibai/tiny-budget#install)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://github.com/hussain-alsaibai/tiny-budget#install)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## LLM Cost Tracking for AI Agents

`tiny-budget` is a dependency-free Python library that tracks per-call LLM
spend across providers, models, and operations. It was built for **multi-model
AI agents** like [OpenClaw](https://github.com/hussain-alsaibai) that route work
across Kimi K2.6, Nemotron, GLM, Qwen, Gemini, GPT, and DeepSeek — where cost
attribution per model is the only way to keep a budget honest.

- **Zero dependencies** — pure stdlib (`json`, `pathlib`, `dataclasses`).
- **JSON-persisted** — survives restarts, single-file, easy to inspect.
- **Three breakdowns** — by provider, by model, by operation.
- **Tiny API surface** — `track`, `total_cost`, `get_summary`, `reset`.

## Installation

```bash
pip install tiny-budget
```

## Usage

```python
from tiny_budget import CostBudget

budget = CostBudget()  # loads ~/.tiny-budget.json by default

# Record each LLM call as it happens
budget.track(
    provider="openai",
    model="gpt-4o",
    operation="summarize",
    tokens_in=1200,
    tokens_out=400,
    latency_ms=1820,
    cost_usd=0.0134,
)

budget.track(
    provider="deepseek",
    model="deepseek-chat",
    operation="summarize",
    tokens_in=1200,
    tokens_out=400,
    latency_ms=940,
    cost_usd=0.0004,
)

# Aggregations
print(f"Total spent: ${budget.total_cost():.4f}")
print(f"Tokens: {budget.total_tokens()}")

for provider, cost in budget.get_by_provider().items():
    print(f"  {provider}: ${cost:.4f}")

for model, cost in budget.get_by_model().items():
    print(f"  {model}: ${cost:.4f}")

print(budget.get_summary())

# Start a new accounting window
budget.reset()
```

A custom storage path is one argument away:

```python
budget = CostBudget(path="./my-project/budget.json")
```

## Design Rationale

Multi-model agents don't fail loudly — they fail expensively. A router that
prefers a 70B-class model for trivial lookups can burn a daily budget before
breakfast. `tiny-budget` exists to make that *visible*:

1. **Per-model attribution.** `get_by_model()` lets you see that Kimi K2.6
   is 40× cheaper than GPT-4o for the same `summarize` operation — and then
   adjust routing.
2. **Per-operation attribution.** `get_by_operation()` separates system
   prompts from tool calls from user-facing generations, so you can price
   each layer independently.
3. **Stdlib only, single-file JSON.** No SQLite, no daemon, no network. It
   runs in CI, in a Lambda, in an air-gapped dev box. You can `cat` the
   budget file and reason about it.
4. **Append on every call.** Writes are O(1) and atomic-ish (write-truncate);
   you never lose a tracked call because the process died.
5. **Graceful missing keys.** Aggregations default to `0.0` / `{}` so a half-
   formed record never crashes an agent loop.

## API Reference

### `CostBudget(path: str | Path = "~/.tiny-budget.json")`

| Method                                | Returns                | Description                                |
|---------------------------------------|------------------------|--------------------------------------------|
| `track(provider, model, operation, tokens_in=0, tokens_out=0, latency_ms=0.0, cost_usd=0.0)` | `dict` | Record a single LLM call. Persists immediately. |
| `total_cost()`                        | `float`                | Total USD across all records.              |
| `total_tokens()`                      | `dict{in: int, out: int}` | Token totals.                           |
| `get_by_model()`                      | `dict[str, float]`     | `model → cost_usd`                         |
| `get_by_operation()`                  | `dict[str, float]`     | `operation → cost_usd`                     |
| `get_by_provider()`                   | `dict[str, float]`     | `provider → cost_usd`                      |
| `get_summary()`                       | `dict`                 | Full stats: counts, totals, breakdowns.    |
| `reset()`                             | `None`                 | Clear all records, persist empty file.     |

All aggregation methods gracefully skip records with missing `provider`,
`model`, or `operation` keys.

## License

MIT — see [LICENSE](LICENSE).