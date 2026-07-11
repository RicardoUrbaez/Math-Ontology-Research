# Rapid Pilot Runner

This folder stores real rapid-pilot responses collected by `scripts/run_rapid_pilot.py`.

## Run

```powershell
.\.venv\Scripts\python.exe scripts\run_rapid_pilot.py
```

Open `http://127.0.0.1:8765`, give each participant one link, and do not collect names.

## Finalize

After at least two complete participants:

```powershell
.\.venv\Scripts\python.exe scripts\finalize_rapid_pilot.py
```

That creates:

- `study/rapid_pilot/responses.jsonl`
- `study/rapid_pilot/rapid_pilot_results.xlsx`
- `study/rapid_pilot/rapid_pilot_comprehension_scores.csv`
- `study/rapid_pilot/rapid_pilot_nasa_tlx.csv`
- `study/rapid_pilot/rapid_pilot_interview_coding.csv`

The finalize step then regenerates the Week 6 statistics, figures, and paper sections from the rapid-pilot workbook.
