from __future__ import annotations

import pytest

from exa_demo.cost_model import enforce_budget, estimate_cost_from_pricing


def test_estimate_cost_accounts_for_search_and_contents() -> None:
    pricing = {
        "search_1_25": 0.005,
        "search_26_100": 0.025,
        "deep_search_1_25": 0.012,
        "deep_reasoning_search_1_25": 0.015,
        "content_text_per_page": 0.001,
        "content_highlights_per_page": 0.001,
        "content_summary_per_page": 0.001,
    }
    payload = {
        "contents": {
            "text": True,
            "highlights": {"highlightsPerUrl": 1, "numSentences": 2},
        }
    }

    assert estimate_cost_from_pricing(payload, 5, pricing, 100) == 0.015


def test_estimate_cost_uses_search_type_specific_tiers() -> None:
    pricing = {
        "search_1_25": 0.005,
        "search_26_100": 0.025,
        "deep_search_1_25": 0.012,
        "deep_search_26_100": 0.03,
        "deep_reasoning_search_1_25": 0.015,
        "deep_reasoning_search_26_100": 0.04,
        "content_text_per_page": 0.001,
        "content_highlights_per_page": 0.001,
        "content_summary_per_page": 0.001,
    }

    deep_payload = {"type": "deep"}
    deep_reasoning_payload = {"type": "deep-reasoning"}
    fallback_payload = {"type": "auto"}

    assert estimate_cost_from_pricing(deep_payload, 5, pricing, 100) == 0.012
    assert estimate_cost_from_pricing(deep_payload, 26, pricing, 100) == 0.03
    assert estimate_cost_from_pricing(deep_reasoning_payload, 5, pricing, 100) == 0.015
    assert estimate_cost_from_pricing(fallback_payload, 5, pricing, 100) == 0.005


def test_enforce_budget_blocks_projected_overspend() -> None:
    with pytest.raises(RuntimeError, match="Budget cap exceeded"):
        enforce_budget(0.02, spent_usd=0.04, budget_cap_usd=0.05, run_id="demo-run")
