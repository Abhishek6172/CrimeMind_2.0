# Execution guide

Prerequisites: Python 3.11+, PostgreSQL 16 reachable as the admin URL in `CM_ADMIN_URL_BASE` (default `postgresql://postgres:postgres@localhost:5432`), `pip install -r backend/requirements.txt -r research/requirements-research.txt`.
The research code creates and drops **disposable** databases named `cm_rw_*`, `cm_p7*`; it never touches the application database.

## Everything
```
python -m research.run_all --phases 3 4 5 6 7 8
```
Options: `--seeds 2026-2075` (phases 3–5), `--workers 3`, `--quick` (smoke run into a scratch directory; official results untouched), `--dry-run` (print commands), `--out DIR`.
Per-step logs and `run_all_manifest.json` are written to `research/phase8/results/<run id>/`.

## Single phases
| Phase | Run | Report |
|---|---|---|
| 3 | `python -m research.phase3.run_phase3` | `python research/phase3/reports/make_report.py` |
| 4 | `python -m research.phase4.run_phase4` | `python research/phase4/reports/make_report.py` |
| 5 | `python -m research.phase5.run_phase5` then `python -m research.phase5.analyse` | `python research/phase5/make_report.py` |
| 6 | `python -m research.phase6.benchmark.build_benchmark`, `python -m research.phase6.run_phase6`, `python -m research.phase6.provider_eval` | `python research/phase6/reports/make_report.py` |
| 7 | `python -m research.phase7.run_phase7` | `python research/phase7/reports/make_docs.py` and `make_report.py` |
| 8 | `python -m research.phase8.plots`, `python research/phase8/build_final_report.py` | – |

## Tests
`python -m pytest backend/tests` and `python -m pytest research` (the latter needs PostgreSQL).

## Windows (PowerShell)
```
$env:CM_ADMIN_URL_BASE = "postgresql://postgres:postgres@localhost:5432"
python -m research.run_all --quick
```
No `fcntl`, shell pipelines or POSIX paths are used (file locking is portable; paths via `pathlib`). If PostgreSQL runs in Docker, publish port 5432 and use the same URL. Windows has not been exercised in this repository's CI; only Linux was run.

## Live LLM evaluation (optional)
Set `GEMINI_API_KEY` and/or `ANTHROPIC_API_KEY` in your environment (never in source), then `python -m research.phase6.provider_eval --sample 20`. Without keys the report states NOT RUN.
