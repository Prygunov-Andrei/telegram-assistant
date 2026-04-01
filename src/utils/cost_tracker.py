from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PRICES_PER_1M = {
    "claude-opus-4-6": {"input": 5.0, "output": 25.0, "cached": 0.50},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cached": 0.30},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0, "cached": 0.10},
}


@dataclass
class UsageRecord:
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float


@dataclass
class CostTracker:
    usage_dir: str = "memory/usage"
    daily_limit_usd: float = 5.0
    _today_records: list[UsageRecord] = field(default_factory=list, init=False)
    _today_date: str = field(default="", init=False)

    def __post_init__(self) -> None:
        Path(self.usage_dir).mkdir(parents=True, exist_ok=True)
        self._today_date = date.today().isoformat()

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int, cached_tokens: int) -> float:
        prices = PRICES_PER_1M.get(model, PRICES_PER_1M["claude-haiku-4-5-20251001"])
        cost = (
            (input_tokens / 1_000_000) * prices["input"]
            + (output_tokens / 1_000_000) * prices["output"]
            + (cached_tokens / 1_000_000) * prices["cached"]
        )
        return round(cost, 6)

    def record(self, model: str, usage: dict[str, Any]) -> UsageRecord:
        today = date.today().isoformat()
        if today != self._today_date:
            self._today_records = []
            self._today_date = today

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cached_tokens = usage.get("cache_read_input_tokens", 0)

        cost = self._calculate_cost(model, input_tokens, output_tokens, cached_tokens)

        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost_usd=cost,
        )
        self._today_records.append(record)

        log_file = Path(self.usage_dir) / f"{today}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": record.timestamp,
                "model": record.model,
                "in": record.input_tokens,
                "out": record.output_tokens,
                "cached": record.cached_tokens,
                "cost": record.cost_usd,
            }) + "\n")

        return record

    def today_cost(self) -> float:
        today = date.today().isoformat()
        if today != self._today_date:
            self._today_records = []
            self._today_date = today
        return round(sum(r.cost_usd for r in self._today_records), 4)

    def is_over_limit(self) -> bool:
        return self.today_cost() > self.daily_limit_usd

    def summary(self) -> dict[str, Any]:
        today_cost = self.today_cost()
        today_requests = len(self._today_records)
        today_tokens = sum(r.input_tokens + r.output_tokens + r.cached_tokens for r in self._today_records)

        model_breakdown: dict[str, dict[str, Any]] = {}
        for r in self._today_records:
            if r.model not in model_breakdown:
                model_breakdown[r.model] = {"requests": 0, "cost_usd": 0.0}
            model_breakdown[r.model]["requests"] += 1
            model_breakdown[r.model]["cost_usd"] = round(
                model_breakdown[r.model]["cost_usd"] + r.cost_usd, 4
            )

        return {
            "today": {
                "requests": today_requests,
                "tokens": today_tokens,
                "cost_usd": today_cost,
                "limit_usd": self.daily_limit_usd,
            },
            "model_breakdown": model_breakdown,
        }
