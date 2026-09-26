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
if "notice_log" not in st.session_state:
    st.session_state.notice_log = []
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
    low_col, high_col = st.columns(2)
    with low_col:
        low = st.number_input(
            "Low % (inclusive)", min_value=0.0, max_value=100.0,
            value=0.0, step=0.01, format="%.2f",
        )
    with high_col:
        high = st.number_input(
            "High % (inclusive)", min_value=0.0, max_value=100.0,
            value=75.0, step=0.01, format="%.2f",
        )
    if low > high:
        st.warning("Low % is greater than High % — swap them or the report will come back empty.")

    st.header("3. Filters")

    # Everything below is populated straight from whatever file you just
    # uploaded — department codes AND subject names — so this same app
    # works unmodified for BCA, MCA, or any other department/program: it
    # never hardcodes a department or subject list, it reads them fresh
    # from your file every time.
    G_preview, C_preview = None, None
    if raw_file is not None:
        try:
            preview_path = os.path.join(WORKDIR, "_preview.xlsx")
            with open(preview_path, "wb") as f:
                f.write(raw_file.getbuffer())
            G_preview, C_preview = vp.load_raw(preview_path)
        except Exception:
            pass  # fall back to empty dropdowns — the real error surfaces clearly on Run

    available_depts = ["ALL"]
    if G_preview:
        available_depts += sorted({r["_dept"] for r in G_preview if r.get("_dept")})
    dept = st.selectbox(
        "Department", options=available_depts, index=0,
        help="Populated from the uploaded file once you add it above. 'ALL' keeps every department.",
    )

    include_soft_skill = st.checkbox("Include Soft Skill", value=True)

    # Subject lists narrow to the selected department automatically, so
    # you're only ever picking from subjects that actually exist there.
    available_subjects = []
    if G_preview:
        subj_col = C_preview["subject"]
        available_subjects = sorted({
            r[subj_col] for r in G_preview
            if r.get(subj_col) and (dept == "ALL" or r.get("_dept") == dept)
        })

    include_selected = st.multiselect(
        "Include only these subjects (whitelist)",
        options=available_subjects, default=[], accept_new_options=True,
        help="Pick from the dropdown, or type a name and press Enter to add it manually "
             "(comma-separated text works too). Leave empty to keep all subjects.",
    )
    exclude_selected = st.multiselect(
        "Exclude these subjects (blacklist)",
        options=available_subjects, default=[], accept_new_options=True,
        help="Pick from the dropdown, or type a name and press Enter to add it manually "
             "(comma-separated text works too). Applied after the whitelist above.",
    )

    st.header("4. Downstream reports")
    build_debar = st.checkbox("Build Tentative Debar List", value=True)
    build_notice_board = st.checkbox(
        "Build Notice Board copy of Debar List", value=True,
        help="Same debar list, print-friendly for posting: no legend/signature "
             "table, no per-subject footer summary row, bigger fonts and row "
             "spacing. Requires 'Build Tentative Debar List' above.",
    )
    notice_font_scale, notice_row_scale = 1.6, 1.6
    if build_notice_board:
        nb_col1, nb_col2 = st.columns(2)
        with nb_col1:
            notice_font_scale = st.number_input(
                "Notice board font scale", min_value=1.0, max_value=3.0,
                value=1.6, step=0.1,
            )
        with nb_col2:
            notice_row_scale = st.number_input(
                "Notice board row-height scale", min_value=1.0, max_value=3.0,
                value=1.6, step=0.1,
            )
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
    st.session_state.notice_log = []
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
    st.session_state.notice_log = []
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

                # Each selected/typed entry is further split on commas, so
                # a manually-typed "A, B, C" (added as one new option) is
                # expanded into three separate subjects too.
                exclude = [s.strip() for item in exclude_selected for s in str(item).split(",") if s.strip()]
                include = [s.strip() for item in include_selected for s in str(item).split(",") if s.strip()]

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

                    # 2b) Notice Board copy — same source, no legend/summary,
                    # bigger fonts/rows. This is a separate call, not a
                    # side effect of the one above, so it's skipped
                    # cleanly if the checkbox is off.
                    if build_notice_board:
                        st.write("⏳ Building Notice Board copy of Debar List…")
                        notice_output = os.path.join(WORKDIR, "Debar_List_NoticeBoard.xlsx")
                        n_out, n_log = vp.build_debar_list(
                            out_path, notice_output, as_of_date or None,
                            notice_board=True,
                            font_scale=notice_font_scale, row_scale=notice_row_scale,
                        )
                        st.session_state.results["Debar List (Notice Board)"] = n_out
                        st.session_state.notice_log = n_log
                        st.write("✅ Notice Board copy done")

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

    if st.session_state.notice_log:
        with st.expander("Notice Board copy — build log"):
            for sheet_name, ok, detail in st.session_state.notice_log:
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
