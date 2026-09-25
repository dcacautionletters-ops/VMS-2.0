#!/usr/bin/env python3
"""
VMS Report Studio — Streamlit front-end for vms_pipeline.py
=============================================================
Wraps the FORMATTING side of the pipeline only:
    - VMS Report  (build_report)
    - Tentative Debar List  (build_debar_list)
    - Abstract Workbook  (build_abstract)

This app only wraps the formatting side of the pipeline — there is no
login or download automation in vms_pipeline.py at all; you upload the
raw file(s) yourself and this app does the rest.
"""
import os
import shutil
import tempfile
import time
import traceback

import streamlit as st

import vms_pipeline as vp

st.set_page_config(page_title="VMS Report Studio", page_icon="📊", layout="wide")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(APP_DIR, "presidency_logo.jpg")

# ─────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
with col_title:
    st.title("VMS Report Studio")
    st.caption(
        "Upload the raw consolidated course-wise attendance report and generate the "
        "formatted VMS Report, Tentative Debar List, and (optionally) the Abstract workbook. "
        "Login/download automation is intentionally not part of this app — bring your own raw export."
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────
# Session state for generated outputs
# ─────────────────────────────────────────────────────────────────────
if "workdir" not in st.session_state:
    st.session_state.workdir = tempfile.mkdtemp(prefix="vms_session_")
if "results" not in st.session_state:
    st.session_state.results = {}  # label -> path
if "summaries" not in st.session_state:
    st.session_state.summaries = []
if "debar_log" not in st.session_state:
    st.session_state.debar_log = []
if "abstract_sems" not in st.session_state:
    st.session_state.abstract_sems = []
if "log_lines" not in st.session_state:
    st.session_state.log_lines = []

WORKDIR = st.session_state.workdir

# ─────────────────────────────────────────────────────────────────────
# Sidebar — inputs & options
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("1. Upload files")
    raw_file = st.file_uploader(
        "Raw consolidated course-wise report (.xlsx)",
        type=["xlsx"],
        help="The unmodified export you already downloaded — same format as Linways' "
             "'Consolidated Course Wise Report'.",
    )
    batch_file = st.file_uploader(
        "Lab Batch List workbook (.xlsx) — optional",
        type=["xlsx"],
        help="Only needed to cross-reference lab/internship faculty & batch, and to "
             "unlock the Abstract workbook. Leave empty to skip.",
    )

    st.header("2. Attendance range")
    low, high = st.slider(
        "Show students with attendance % between",
        min_value=0.0, max_value=100.0, value=(0.0, 75.0), step=0.5,
    )

    st.header("3. Filters")
    dept = st.text_input("Department", value="ALL", help="e.g. BCA, MCA, or ALL")
    include_soft_skill = st.checkbox("Include Soft Skill", value=True)
    include_subjects = st.text_input(
        "Include only these subjects (comma-separated)", value="",
        help="Whitelist — leave blank to keep all subjects.",
    )
    exclude_subjects = st.text_input(
        "Exclude these subjects (comma-separated)", value="",
        help="Blacklist — applied after the whitelist above.",
    )

    st.header("4. Downstream reports")
    build_debar = st.checkbox("Build Tentative Debar List", value=True)
    build_abstract = st.checkbox(
        "Build Abstract Workbook", value=True,
        help="Requires a Lab Batch List upload above.",
    )
    program = st.text_input("Program (for Abstract heading)", value="BCA")
    as_of_date = st.text_input(
        "'As of' date (dd.mm.yyyy)", value=time.strftime("%d.%m.%Y"),
        help="Shown on the Debar List and Abstract workbook. Leave as today's date or edit.",
    )

    st.divider()
    run_clicked = st.button("🚀 Run pipeline", type="primary", use_container_width=True)
    reset_clicked = st.button("Clear results", use_container_width=True)

if reset_clicked:
    st.session_state.results = {}
    st.session_state.summaries = []
    st.session_state.debar_log = []
    st.session_state.abstract_sems = []
    st.session_state.log_lines = []
    st.rerun()

# ─────────────────────────────────────────────────────────────────────
# Run pipeline
# ─────────────────────────────────────────────────────────────────────
def save_upload(uploaded, dest_name):
    dest = os.path.join(WORKDIR, dest_name)
    with open(dest, "wb") as f:
        f.write(uploaded.getbuffer())
    return dest


if run_clicked:
    st.session_state.results = {}
    st.session_state.summaries = []
    st.session_state.debar_log = []
    st.session_state.abstract_sems = []
    st.session_state.log_lines = []

    if raw_file is None:
        st.error("Please upload the raw consolidated course-wise report first.")
    else:
        with st.status("Running pipeline…", expanded=True) as status:
            try:
                raw_path = save_upload(raw_file, "raw_input.xlsx")
                st.write("✅ Raw report saved")

                batch_path = None
                if batch_file is not None:
                    batch_path = save_upload(batch_file, "batch_list.xlsx")
                    st.write("✅ Lab Batch List saved")

                exclude = [s.strip() for s in exclude_subjects.split(",") if s.strip()]
                include = [s.strip() for s in include_subjects.split(",") if s.strip()]

                # 1) VMS Report
                st.write("⏳ Building VMS Report…")
                vms_output = os.path.join(WORKDIR, "VMS_Report.xlsx")
                out_path, summaries = vp.build_report(
                    raw_path, vms_output,
                    low=low, high=high, dept=dept or "ALL",
                    exclude=exclude, include=include,
                    include_soft_skill=include_soft_skill,
                    batch_list_path=batch_path,
                )
                st.session_state.results["VMS Report"] = out_path
                st.session_state.summaries = summaries
                st.write(f"✅ VMS Report done — {len(summaries)} section(s)")

                # 2) Debar List
                if build_debar:
                    st.write("⏳ Building Tentative Debar List…")
                    debar_output = os.path.join(WORKDIR, "Debar_List.xlsx")
                    d_out, d_log = vp.build_debar_list(out_path, debar_output, as_of_date or None)
                    st.session_state.results["Debar List"] = d_out
                    st.session_state.debar_log = d_log
                    st.write("✅ Debar List done")

                # 3) Abstract
                if build_abstract:
                    if not batch_path:
                        st.write("⚠️ Skipped Abstract workbook — no Lab Batch List uploaded.")
                    else:
                        st.write("⏳ Building Abstract workbook…")
                        abstract_output = os.path.join(WORKDIR, "Abstract_Report.xlsx")
                        a_out, sems = vp.build_abstract(
                            raw_path, batch_path, abstract_output,
                            date_str=as_of_date or None, program=program or "BCA",
                        )
                        st.session_state.results["Abstract Report"] = a_out
                        st.session_state.abstract_sems = sems
                        st.write("✅ Abstract workbook done")

                status.update(label="Pipeline complete", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Pipeline failed", state="error")
                st.error(f"Something went wrong: {e}")
                with st.expander("Full error details"):
                    st.code(traceback.format_exc())

# ─────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────
if st.session_state.results:
    st.subheader("Results")

    if st.session_state.summaries:
        with st.expander(f"VMS Report — {len(st.session_state.summaries)} section(s)", expanded=True):
            st.dataframe(st.session_state.summaries, use_container_width=True)

    if st.session_state.debar_log:
        with st.expander("Debar List — build log"):
            for sheet_name, ok, detail in st.session_state.debar_log:
                st.write(("✅" if ok else "⏭️") + f" **{sheet_name}** — {detail}")

    if st.session_state.abstract_sems:
        with st.expander("Abstract Workbook — semesters"):
            for s in st.session_state.abstract_sems:
                st.write(f"• SUB {vp.sem_label(s)} SEM")

    st.divider()
    st.subheader("Downloads")
    dl_cols = st.columns(len(st.session_state.results))
    for col, (label, path) in zip(dl_cols, st.session_state.results.items()):
        with col:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    st.download_button(
                        f"⬇️ {label}",
                        data=f.read(),
                        file_name=os.path.basename(path),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
            else:
                st.warning(f"{label} file not found on disk.")
else:
    st.info("Upload the raw report on the left, set your options, and click **Run pipeline**.")
