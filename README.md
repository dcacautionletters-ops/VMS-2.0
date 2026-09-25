# VMS Report Studio

A Streamlit front-end for `vms_pipeline.py` — **formatting only**. There is
no login or browser-automation code in this repo at all; you upload the raw
file(s) yourself and the app runs the rest.

## What it does

1. Upload the raw **consolidated course-wise attendance report** (.xlsx).
2. Optionally upload a **Lab Batch List** workbook to unlock lab/internship
   faculty cross-referencing and the Abstract workbook.
3. Set the attendance % range, department, subject include/exclude lists,
   and whether to include Soft Skill.
4. Click **Run pipeline** to generate:
   - **VMS Report** — GEN / GEN ALL / per-section sheets + summary
   - **Tentative Debar List** (optional, on by default)
   - **Abstract Workbook** (optional, needs the Batch List upload)
5. Download each generated workbook straight from the browser.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

## Files

- `app.py` — the Streamlit UI
- `vms_pipeline.py` — your original pipeline (unmodified)
- `presidency_logo.jpg` — college logo, used in the header and in generated
  Debar List sheets (the pipeline expects it at this exact path/filename)
- `requirements.txt`

## Notes

- Generated files land in a temp folder per session and are offered back to
  you as download buttons — nothing is emailed or uploaded anywhere.
- `vms_pipeline.py` can also be run standalone from the command line —
  `python vms_pipeline.py format ...`, `debar ...`, or `abstract ...` —
  see the docstring at the top of the file for exact usage.
