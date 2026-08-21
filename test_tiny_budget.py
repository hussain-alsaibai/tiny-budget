"""
Tests for tiny-budget. Stdlib only — uses unittest.
"""

import json
import tempfile
import unittest
from pathlib import Path

from tiny_budget import CostBudget


class TempBudget(unittest.TestCase):
    """Each test gets an isolated JSON file in a temp dir."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "budget.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()


class TestTrack(TempBudget):
    def test_track_a_call_and_check_totals(self) -> None:
        b = CostBudget(path=self.path)
        b.track("openai", "gpt-4o", "summarize", 100, 50, 200, 0.01)
        self.assertEqual(b.total_cost(), 0.01)
        self.assertEqual(b.total_tokens(), {"in": 100, "out": 50})

    def test_record_is_persisted_immediately(self) -> None:
        b = CostBudget(path=self.path)
        b.track("deepseek", "deepseek-chat", "qa", 10, 20, 50, 0.0001)
        # New instance loads from same file
        b2 = CostBudget(path=self.path)
        self.assertEqual(len(b2.records), 1)
        self.assertEqual(b2.total_cost(), 0.0001)


class TestAggregations(TempBudget):
    def test_multiple_calls_per_model_breakdown(self) -> None:
        b = CostBudget(path=self.path)
        b.track("openai", "gpt-4o", "summarize", 100, 50, 200, 0.01)
        b.track("openai", "gpt-4o", "qa", 200, 100, 300, 0.02)
        b.track("deepseek", "deepseek-chat", "qa", 200, 100, 300, 0.0004)

        by_model = b.get_by_model()
        self.assertAlmostEqual(by_model["gpt-4o"], 0.03)
        self.assertAlmostEqual(by_model["deepseek-chat"], 0.0004)
        self.assertEqual(len(by_model), 2)

    def test_multiple_calls_per_operation_breakdown(self) -> None:
        b = CostBudget(path=self.path)
        b.track("openai", "gpt-4o", "summarize", 100, 50, 200, 0.01)
        b.track("deepseek", "deepseek-chat", "summarize", 100, 50, 200, 0.0004)
        b.track("openai", "gpt-4o", "qa", 200, 100, 300, 0.02)

        by_op = b.get_by_operation()
        self.assertAlmostEqual(by_op["summarize"], 0.0104)
        self.assertAlmostEqual(by_op["qa"], 0.02)

    def test_per_provider_breakdown(self) -> None:
        b = CostBudget(path=self.path)
        b.track("openai", "gpt-4o", "summarize", 100, 50, 200, 0.01)
        b.track("deepseek", "deepseek-chat", "qa", 100, 50, 200, 0.0004)
        b.track("kimi", "kimi-k2.6", "embed", 100, 50, 200, 0.0002)

        by_provider = b.get_by_provider()
        self.assertAlmostEqual(by_provider["openai"], 0.01)
        self.assertAlmostEqual(by_provider["deepseek"], 0.0004)
        self.assertAlmostEqual(by_provider["kimi"], 0.0002)

    def test_summary_shape(self) -> None:
        b = CostBudget(path=self.path)
        b.track("openai", "gpt-4o", "summarize", 100, 50, 200, 0.01)

        s = b.get_summary()
        self.assertEqual(s["calls"], 1)
        self.assertAlmostEqual(s["total_cost_usd"], 0.01)
        self.assertEqual(s["total_tokens"], {"in": 100, "out": 50})
        self.assertIn("by_provider", s)
        self.assertIn("by_model", s)
        self.assertIn("by_operation", s)


class TestReset(TempBudget):
    def test_reset_clears_data(self) -> None:
        b = CostBudget(path=self.path)
        b.track("openai", "gpt-4o", "summarize", 100, 50, 200, 0.01)
        b.track("deepseek", "deepseek-chat", "qa", 50, 25, 100, 0.0002)
        self.assertEqual(len(b.records), 2)

        b.reset()
        self.assertEqual(b.records, [])
        self.assertEqual(b.total_cost(), 0.0)
        self.assertEqual(b.total_tokens(), {"in": 0, "out": 0})
        self.assertEqual(b.get_by_model(), {})

        # persisted, not just in-memory
        b2 = CostBudget(path=self.path)
        self.assertEqual(b2.records, [])


class TestGracefulDegradation(TempBudget):
    def test_missing_keys_return_zero_or_empty(self) -> None:
        b = CostBudget(path=self.path)
        # Manually inject a half-formed record
        b.records.append({"timestamp": "2026-01-01T00:00:00Z", "cost_usd": 0.05})
        # cost_usd is present so total_cost includes it
        self.assertAlmostEqual(b.total_cost(), 0.05)
        # missing provider/model/operation → empty breakdowns
        self.assertEqual(b.get_by_provider(), {})
        self.assertEqual(b.get_by_model(), {})
        self.assertEqual(b.get_by_operation(), {})

    def test_empty_budget_returns_zero_or_empty(self) -> None:
        b = CostBudget(path=self.path)
        self.assertEqual(b.total_cost(), 0.0)
        self.assertEqual(b.total_tokens(), {"in": 0, "out": 0})
        self.assertEqual(b.get_by_model(), {})
        self.assertEqual(b.get_by_operation(), {})
        self.assertEqual(b.get_by_provider(), {})
        s = b.get_summary()
        self.assertEqual(s["calls"], 0)
        self.assertEqual(s["total_cost_usd"], 0.0)

    def test_corrupt_file_does_not_crash(self) -> None:
        self.path.write_text("not valid json {{{", encoding="utf-8")
        b = CostBudget(path=self.path)
        self.assertEqual(b.records, [])
        # Still usable
        b.track("openai", "gpt-4o", "summarize", 100, 50, 200, 0.01)
        self.assertEqual(len(b.records), 1)


class TestRequiredFields(TempBudget):
    def test_provider_and_model_are_recorded(self) -> None:
        b = CostBudget(path=self.path)
        rec = b.track("anthropic", "claude-3.5-sonnet", "summarize", 10, 5, 100, 0.001)
        self.assertEqual(rec["provider"], "anthropic")
        self.assertEqual(rec["model"], "claude-3.5-sonnet")
        self.assertEqual(rec["operation"], "summarize")
        self.assertIn("timestamp", rec)
        # ISO 8601 with timezone
        self.assertIn("T", rec["timestamp"])


if __name__ == "__main__":
    unittest.main()