# CrimeMind — Research Lab + Casework + Training Case

This merged package combines:
- The original CrimeMind project and authenticated backend-connected casework UI from `crimemind_phase3_8.zip`.
- The interactive Research Lab UI and saved Phase 3–8 research dashboards from `CrimeMind_ResearchLab_Integrated.zip`.
- Fictional training case CF-2026-014 with five evidence items.

## Run the backend
Open PowerShell in `crimemind/backend`:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Configure backend/.env using your existing database and Gemini settings.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8077 --reload
```
If your virtual environment already exists, activate it instead of recreating it.

## Run the frontend
Open a second PowerShell in `crimemind/frontend`:
```powershell
npm install
npm run dev -- --host 127.0.0.1 --port 5176
```
Open `http://127.0.0.1:5176`.

## Navigation
- Research Lab opens first.
- Use **Open casework app** to open the original authenticated CrimeMind casework UI.
- In Research Lab, use **Training case** to inspect fictional case CF-2026-014 and its five evidence records.

## Training case
The case is preserved under:
- `research/cases/CF-2026-014/`
- `frontend/public/research/cases/CF-2026-014/`
- Browser-readable dashboard bundle: `frontend/public/research/data/training_case.json`

The case is fictional. The dashboard is read-only and does not insert this training case into the live PostgreSQL case database. To import it as a live case, a separate validated importer/API workflow is required.

## Research data provenance
The Research Lab's static dashboard exports are retained from the supplied integrated research package. Their underlying research snapshot is identified in `RESEARCH_LAB_INTEGRATION.md`. If you want the dashboard to show a later research run, regenerate the static exports from that run.
