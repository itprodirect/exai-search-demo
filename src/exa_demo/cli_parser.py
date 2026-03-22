from __future__ import annotations

import argparse
from typing import Any, Callable, Dict, Mapping

from .config import default_config
from .ranked_workflows import LEGACY_DEFAULT_SUITE_ALIAS, benchmark_suite_choices


def build_parser(*, handlers: Mapping[str, Callable[..., int]]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI for the exai-insurance-intel toolkit."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Run a single search query.")
    _add_common_runtime_args(search_parser)
    _add_common_search_args(search_parser)
    search_parser.add_argument("query", help="Query string to send to Exa.")
    search_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit structured JSON instead of a text summary.",
    )
    search_parser.set_defaults(handler=handlers["search"])

    eval_parser = subparsers.add_parser("eval", help="Run the benchmark evaluation suite.")
    _add_common_runtime_args(eval_parser)
    _add_common_search_args(eval_parser)
    eval_parser.add_argument(
        "--suite",
        default=LEGACY_DEFAULT_SUITE_ALIAS,
        choices=benchmark_suite_choices(),
        help="Named benchmark suite to run.",
    )
    eval_parser.add_argument(
        "--queries-file",
        help="Optional JSON file containing an array of query strings.",
    )
    eval_parser.add_argument(
        "--limit",
        type=int,
        help="Optional cap on the number of benchmark queries to execute.",
    )
    eval_parser.add_argument(
        "--compare-to-run-id",
        help="Optional baseline run id for before/after comparison reporting.",
    )
    eval_parser.add_argument(
        "--compare-base-dir",
        help="Optional base artifact directory for --compare-to-run-id. Defaults to --artifact-dir.",
    )
    eval_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit summary JSON instead of a text summary.",
    )
    eval_parser.set_defaults(handler=handlers["eval"])

    answer_parser = subparsers.add_parser("answer", help="Run a cited-answer query.")
    _add_common_runtime_args(answer_parser)
    answer_parser.add_argument("query", help="Question to send to Exa.")
    answer_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit structured JSON instead of a text summary.",
    )
    answer_parser.set_defaults(handler=handlers["answer"])

    research_parser = subparsers.add_parser(
        "research", help="Run a report-style research query."
    )
    _add_common_runtime_args(research_parser)
    research_parser.add_argument("query", help="Research prompt to send to Exa.")
    research_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit structured JSON instead of a text summary.",
    )
    research_parser.set_defaults(handler=handlers["research"])

    find_similar_parser = subparsers.add_parser(
        "find-similar",
        help="Run a seed-URL similarity query.",
    )
    _add_common_runtime_args(find_similar_parser)
    _add_common_search_args(find_similar_parser)
    find_similar_parser.set_defaults(search_type="deep")
    find_similar_parser.add_argument("url", help="Seed URL to send to Exa.")
    find_similar_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit structured JSON instead of a text summary.",
    )
    find_similar_parser.set_defaults(handler=handlers["find-similar"])

    structured_parser = subparsers.add_parser(
        "structured-search",
        help="Run a structured-output search query against a JSON schema.",
    )
    _add_common_runtime_args(structured_parser)
    _add_common_search_args(structured_parser)
    structured_parser.set_defaults(search_type="deep")
    structured_parser.add_argument("query", help="Query string to send to Exa.")
    structured_parser.add_argument(
        "--schema-file", required=True, help="Path to a JSON schema file."
    )
    structured_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit structured JSON instead of a text summary.",
    )
    structured_parser.set_defaults(handler=handlers["structured-search"])

    compare_parser = subparsers.add_parser(
        "compare-search-types",
        help="Run the same evaluation suite for two search types and emit a before/after comparison.",
    )
    _add_common_runtime_args(compare_parser)
    _add_common_search_args(compare_parser, include_search_type=False)
    compare_parser.add_argument(
        "--suite",
        default=LEGACY_DEFAULT_SUITE_ALIAS,
        choices=benchmark_suite_choices(),
        help="Named benchmark suite to run for both search types.",
    )
    compare_parser.add_argument(
        "--queries-file",
        help="Optional JSON file containing an array of query strings.",
    )
    compare_parser.add_argument(
        "--limit",
        type=int,
        help="Optional cap on the number of benchmark queries to execute.",
    )
    compare_parser.add_argument(
        "--baseline-type",
        default="deep",
        help="Baseline search type to execute first. Defaults to deep.",
    )
    compare_parser.add_argument(
        "--candidate-type",
        default="deep-reasoning",
        help="Candidate search type to execute second. Defaults to deep-reasoning.",
    )
    compare_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit summary JSON instead of a text summary.",
    )
    compare_parser.set_defaults(handler=handlers["compare-search-types"])

    budget_parser = subparsers.add_parser(
        "budget", help="Inspect cached spend metrics."
    )
    budget_parser.add_argument("--run-id", help="Optional run id to scope the budget summary.")
    budget_parser.add_argument(
        "--sqlite-path",
        default="exa_cache.sqlite",
        help="Path to the sqlite cache/ledger database.",
    )
    budget_parser.add_argument(
        "--cache-ttl-hours",
        type=float,
        default=float(default_config()["cache_ttl_hours"]),
        help="TTL to use when opening the cache store.",
    )
    budget_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit JSON instead of text output.",
    )
    budget_parser.set_defaults(handler=handlers["budget"])

    return parser


def apply_search_overrides(
    config: Dict[str, Any], pricing: Dict[str, float], args: argparse.Namespace
) -> None:
    if getattr(args, "num_results", None):
        config["num_results"] = int(args.num_results)
    if getattr(args, "search_type", None):
        config["search_type"] = args.search_type
    if getattr(args, "category", None):
        config["category"] = args.category
    if getattr(args, "sqlite_path", None):
        config["sqlite_path"] = args.sqlite_path
    if getattr(args, "cache_ttl_hours", None) is not None:
        config["cache_ttl_hours"] = float(args.cache_ttl_hours)
    if getattr(args, "budget_cap_usd", None) is not None:
        config["budget_cap_usd"] = float(args.budget_cap_usd)
    if getattr(args, "include_domains", None):
        config["include_domains"] = list(args.include_domains)
    if getattr(args, "exclude_domains", None):
        config["exclude_domains"] = list(args.exclude_domains)
    if getattr(args, "additional_queries", None):
        config["additional_queries"] = _clean_string_list(args.additional_queries)
    if getattr(args, "start_published_date", None):
        config["start_published_date"] = str(args.start_published_date).strip()
    if getattr(args, "end_published_date", None):
        config["end_published_date"] = str(args.end_published_date).strip()
    if getattr(args, "livecrawl", None):
        config["livecrawl"] = True
    if hasattr(args, "use_text") and args.use_text:
        config["use_text"] = True
    if hasattr(args, "use_summary") and args.use_summary:
        config["use_summary"] = True
    if hasattr(args, "no_highlights") and args.no_highlights:
        config["use_highlights"] = False
    _apply_pricing_overrides(pricing, args)


def namespace_with_overrides(
    args: argparse.Namespace, **overrides: Any
) -> argparse.Namespace:
    payload = vars(args).copy()
    payload.update(overrides)
    return argparse.Namespace(**payload)


def run_id_suffix_for_search_type(search_type: str) -> str:
    text = str(search_type or "").strip().lower()
    return text.replace("_", "-")


def _add_common_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode", choices=["smoke", "live", "auto"], default="auto", help="Runtime mode."
    )
    parser.add_argument("--run-id", help="Optional explicit run id.")
    parser.add_argument(
        "--sqlite-path",
        default="exa_cache.sqlite",
        help="Path to the sqlite cache/ledger database.",
    )
    parser.add_argument(
        "--cache-ttl-hours",
        type=float,
        default=float(default_config()["cache_ttl_hours"]),
        help="Cache TTL in hours.",
    )
    parser.add_argument(
        "--artifact-dir", default="experiments", help="Base directory for run artifacts."
    )
    parser.add_argument(
        "--budget-cap-usd", type=float, help="Optional override for the run budget cap."
    )


def _add_common_search_args(
    parser: argparse.ArgumentParser, *, include_search_type: bool = True
) -> None:
    parser.add_argument(
        "--num-results",
        type=int,
        default=int(default_config()["num_results"]),
        help="Number of results to request.",
    )
    if include_search_type:
        parser.add_argument(
            "--type",
            dest="search_type",
            default=default_config()["search_type"],
            help="Exa search type to request.",
        )
    parser.add_argument(
        "--category",
        default=default_config()["category"],
        help="Exa category to request.",
    )
    parser.add_argument("--use-text", action="store_true", help="Include full text in contents.")
    parser.add_argument("--use-summary", action="store_true", help="Include summary in contents.")
    parser.add_argument("--no-highlights", action="store_true", help="Disable highlights in contents.")
    parser.add_argument(
        "--include-domain",
        dest="include_domains",
        action="append",
        default=[],
        help="Domain to include. May be repeated.",
    )
    parser.add_argument(
        "--exclude-domain",
        dest="exclude_domains",
        action="append",
        default=[],
        help="Domain to exclude. May be repeated.",
    )
    parser.add_argument(
        "--additional-query",
        dest="additional_queries",
        action="append",
        default=[],
        help="Additional query hint for deep search. May be repeated.",
    )
    parser.add_argument(
        "--start-published-date",
        help="Optional lower bound for published date filtering (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-published-date",
        help="Optional upper bound for published date filtering (YYYY-MM-DD).",
    )
    parser.add_argument("--livecrawl", action="store_true", help="Force live crawl for the request.")
    parser.add_argument(
        "--search-cost-1-25",
        type=float,
        dest="search_cost_1_25",
        help="Override the base search cost for 1-25 results.",
    )
    parser.add_argument(
        "--search-cost-26-100",
        type=float,
        dest="search_cost_26_100",
        help="Override the base search cost for 26-100 results.",
    )
    parser.add_argument(
        "--deep-search-cost-1-25",
        type=float,
        dest="deep_search_cost_1_25",
        help="Override deep search cost for 1-25 results.",
    )
    parser.add_argument(
        "--deep-search-cost-26-100",
        type=float,
        dest="deep_search_cost_26_100",
        help="Override deep search cost for 26-100 results.",
    )
    parser.add_argument(
        "--deep-reasoning-search-cost-1-25",
        type=float,
        dest="deep_reasoning_search_cost_1_25",
        help="Override deep-reasoning search cost for 1-25 results.",
    )
    parser.add_argument(
        "--deep-reasoning-search-cost-26-100",
        type=float,
        dest="deep_reasoning_search_cost_26_100",
        help="Override deep-reasoning search cost for 26-100 results.",
    )


def _apply_pricing_overrides(pricing: Dict[str, float], args: argparse.Namespace) -> None:
    for arg_name, key in [
        ("search_cost_1_25", "search_1_25"),
        ("search_cost_26_100", "search_26_100"),
        ("deep_search_cost_1_25", "deep_search_1_25"),
        ("deep_search_cost_26_100", "deep_search_26_100"),
        ("deep_reasoning_search_cost_1_25", "deep_reasoning_search_1_25"),
        ("deep_reasoning_search_cost_26_100", "deep_reasoning_search_26_100"),
    ]:
        value = getattr(args, arg_name, None)
        if value is not None:
            pricing[key] = float(value)


def _clean_string_list(values: list[Any]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            cleaned.append(text)
    return cleaned
