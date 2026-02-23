# exai-search-demo

Minimal, reproducible Exa People Search evaluation notebook for insurance / CAT-loss workflows. It is designed to test value + cost before integration into a larger claims or litigation-support system.

Core artifact:

- `exa_people_search_eval.ipynb` (budget-capped, sqlite-cached, public/professional-info-only workflow)

Lean support files:

- `.env` (local only, not committed)
- `.env.example`
- `exa_cache.sqlite` (local sqlite cache, not committed)
- `requirements.txt`
- `scripts/run_notebook_smoke.py`
- `scripts/reset_cache.py`

## What This Evaluates

- People-search relevance for insurance / CAT-loss roles (experts, consultants, attorneys, adjusters)
- Cost per uncached query and projected costs at scale
- Repeatability via sqlite caching (reruns should not re-bill)
- Safe usage patterns (public/professional info only, no doxxing/address hunting)

## Recommended Cheap Defaults

The notebook defaults are set for low-cost triage:

- `highlights` = ON
- `text` = OFF
- `summary` = OFF
- `num_results` = `5`

These settings keep snippets useful while limiting per-result content costs.

## Windows 11 Setup (Python 3.10+)

1. Open PowerShell in the repo folder.
2. Create a virtual environment:

```powershell
py -3.10 -m venv .venv
```

3. Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

4. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Create `.env` From `.env.example`

1. Copy the example file:

```powershell
Copy-Item .env.example .env
```

2. Edit `.env` and set your API key:

```env
EXA_API_KEY=your_real_exa_api_key
EXA_SMOKE_NO_NETWORK=0
```

Notes:

- Keep `.env` local only. It is ignored by `.gitignore`.
- If you want a no-network smoke run (no API key, no billing), set `EXA_SMOKE_NO_NETWORK=1`.

## Run The Notebook

Use either Jupyter Lab or VS Code notebooks.

### Option A: Jupyter Lab

```powershell
jupyter lab
```

Open `exa_people_search_eval.ipynb` and run cells top-to-bottom.

### Option B: VS Code

1. Open the folder in VS Code.
2. Select the `.venv` Python interpreter.
3. Open `exa_people_search_eval.ipynb`.
4. Run all cells.

## Optional Smoke Test Runner

Runs the notebook end-to-end using `nbclient`. If `EXA_API_KEY` is missing, it automatically switches to no-network smoke mode.

```powershell
python .\scripts\run_notebook_smoke.py
```

## Cache Behavior (`exa_cache.sqlite`)

- The notebook stores responses in `exa_cache.sqlite` keyed by a hash of the request payload.
- Re-running the same query/settings returns cached results and records a ledger entry as a cache hit.
- Budget enforcement applies only to uncached calls.
- The notebook also tracks request count, cache hits vs uncached calls, spend so far, and average cost per uncached query.

Reset the cache safely:

```powershell
python .\scripts\reset_cache.py
```

Skip the confirmation prompt:

```powershell
python .\scripts\reset_cache.py --yes
```

## Budget Cap (Hard Stop)

- Default cap is `7.50` USD (`CONFIG["budget_cap_usd"]` in Cell 2).
- Before any uncached Exa request, the notebook estimates the next call cost and stops if it would exceed the cap.
- Cached reruns do not count toward new spend.

## Change Cost Settings Safely

Change these in Cell 2 (`CONFIG`) and rerun from the top:

- `num_results` (largest cost lever)
- `use_highlights`
- `use_text`
- `use_summary`

Guidance:

- Start with `num_results=5`
- Keep `use_highlights=True`
- Keep `use_text=False`
- Keep `use_summary=False`
- Only enable `text`/`summary` for second-pass review on shortlisted queries/results

## Notebook Output (What To Look For)

The notebook prints and/or computes:

- Request count
- Cache hits vs uncached calls
- Spent so far (USD)
- Average cost per uncached query
- Projected costs for `100`, `1,000`, and `10,000` queries
- A decision rubric and integration-point recommendations

## GitHub Sync (If Starting Fresh)

If this folder is not already a git repo:

```powershell
git init
git branch -M main
```

Commit locally:

```powershell
git add .
git commit -m "feat: minimal exa people search eval demo"
```

Set remote and push:

```powershell
git remote add origin https://github.com/itprodirect/exai-search-demo.git
git push -u origin main
```

If `origin` already exists, update it instead:

```powershell
git remote set-url origin https://github.com/itprodirect/exai-search-demo.git
git push -u origin main
```

## Safety / Scope

- Public/professional info only
- No address hunting / doxxing
- Redaction logic remains in place for displayed snippets (emails/phones/street-like addresses)
- Human review required before any operational use
