# Demo Gallery

This page is the docs entrypoint for the shipped workflows. It stays command-first and artifact-first so the repo remains easy to navigate without changing the core harness.

## Discovery

`search` is the default ranked-discovery workflow for CAT-loss and insurance people search. Use it when you want a relevance-ranked result set and the standard `results.jsonl` plus `summary.json` artifact bundle.

```powershell
python -m exa_demo search "forensic engineer insurance expert witness" --mode smoke --json
```

`find-similar` is the seed-URL expansion workflow. Use it when you already have a useful page or profile and want adjacent pages, firms, or experts.

```powershell
python -m exa_demo find-similar "https://example.com/florida-appraisal-decision" --mode smoke --json
```

## Research

`answer` is the cited-answer workflow. Use it for direct lookup questions where a short answer plus citations is enough.

```powershell
python -m exa_demo answer "What is the Florida appraisal clause dispute process?" --mode smoke --json
```

`research` is the report-style workflow. Use it for broader market or regulatory summaries where a longer narrative output is more useful than a single answer.

```powershell
python -m exa_demo research "Summarize the Florida CAT market outlook." --mode smoke --json
```

## Extraction

`structured-search` is the schema-driven extraction workflow. Use it when you want Exa to return a typed payload that can be normalized into downstream tables, graphs, or datasets.

```powershell
python -m exa_demo structured-search "independent adjuster florida catastrophe claims" --schema-file .\path\to\structured-schema.json --mode smoke --json
```

## Comparison

`compare-search-types` is the analysis workflow for comparing `deep` and `deep-reasoning` on the same benchmark suite. Use it when the question is quality versus cost, not just retrieval.

```powershell
python -m exa_demo compare-search-types --mode smoke --suite forensic_and_damage_engineering --baseline-type deep --candidate-type deep-reasoning --limit 5 --json
```

## Artifact Map

| Workflow | Primary artifact |
| --- | --- |
| `search` | `results.jsonl`, `summary.json`, `manifest.json` |
| `answer` | `answer.json`, `summary.json` |
| `research` | `research.json`, `research.md`, `summary.json` |
| `structured-search` | `structured_output.json`, `summary.json` |
| `find-similar` | `find_similar.json`, `summary.json` |
| `compare-search-types` | `comparison.md`, `comparison.json`, `grouped_query_outcomes.csv` plus paired run artifacts |

## Recommended Order

1. Start with `search` if you are validating the core harness or a new query suite.
2. Switch to `answer` or `research` when the question needs a cited response or a narrative report.
3. Use `structured-search` when you need extractable fields instead of prose.
4. Use `find-similar` when you already have a good seed URL.
5. Use `compare-search-types` when you are deciding whether a costlier search mode is actually worth it.
