# exai-search-demo

Minimal, reproducible **Exa People Search evaluation harness** for insurance / CAT-loss workflows.

This repo is intentionally in **minimal mode**:
- one core notebook: `exa_people_search_eval.ipynb`
- one local env file: `.env` (not committed)
- one local sqlite cache: `exa_cache.sqlite` (not committed)

## What This Repo Evaluates

- Query relevance for CAT-loss / insurance professional discovery
- Cost per uncached query and projected spend at scale
- Repeatability via sqlite caching (reruns should not re-bill)
- Safe usage posture (public/professional info only)

## Recommended Cheap Defaults

In Cell 2 (`CONFIG`), start with:
- `use_highlights=True`
- `use_text=False`
- `use_summary=False`
- `num_results=5`

## Windows 11 Setup (Python 3.10+)

1. Open PowerShell in this repo.
2. Create venv:

```powershell
py -3.10 -m venv .venv
```

3. Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

4. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configure Environment

Create `.env` from template:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
EXA_API_KEY=your_real_exa_api_key
EXA_SMOKE_NO_NETWORK=0
# Optional: set a run id label for grouped budget metrics
# EXA_RUN_ID=demo-2026-03-05
```

Notes:
- `.env` is ignored by git.
- If you want no-network testing, use smoke mode (`EXA_SMOKE_NO_NETWORK=1` or runner `--mode smoke`).

## Run Notebook

Open `exa_people_search_eval.ipynb` in Jupyter Lab or VS Code and run top-to-bottom.

Notebook flow is intentionally fixed to 9 cells:
1. Install/import + env load
2. Config
3. Exa call wrapper
4. Cache wrapper (sqlite) + budget enforcement
5. Single query demo
6. Batch query suite
7. Summary + qualitative notes
8. Cost projections
9. Decision rubric + integration recommendations

## Cache + Budget Behavior

- Requests are cached in `exa_cache.sqlite` by payload hash.
- Repeated requests return cache hits and should not re-bill.
- Budget hard stop applies to **uncached calls in current `RUN_ID`**.
- Metrics still include all-time totals for visibility.

Reset cache safely:

```powershell
python .\scripts\reset_cache.py
```

Skip prompt:

```powershell
python .\scripts\reset_cache.py --yes
```

## Smoke Runner (nbclient)

```powershell
python .\scripts\run_notebook_smoke.py --mode smoke
```

Modes:
- `--mode smoke`: forced no-network run (default)
- `--mode live`: real API calls (requires `EXA_API_KEY`)
- `--mode auto`: live if key exists, otherwise smoke

Optional timeout override:

```powershell
python .\scripts\run_notebook_smoke.py --mode smoke --timeout 180
```

## Safe Cost Tuning

In Cell 2 (`CONFIG`), adjust only these first:
- `num_results`
- `use_highlights`
- `use_text`
- `use_summary`

Guidance:
- Keep `num_results` low for first pass
- Keep text/summary off unless needed for second-pass review
- Estimator intentionally rejects unsupported high `num_results` ranges until pricing tiers are updated

## GitHub Sync

If needed:

```powershell
git init
git branch -M main
git add .
git commit -m "feat: minimal exa people search eval harness"
git remote add origin https://github.com/itprodirect/exai-search-demo.git
git push -u origin main
```

If remote already exists:

```powershell
git remote set-url origin https://github.com/itprodirect/exai-search-demo.git
git push -u origin main
```

## Guardrails

- Public/professional info only
- No address hunting / doxxing
- No contact harvesting
- Redaction stays enabled in notebook output
- Human review required before operational use