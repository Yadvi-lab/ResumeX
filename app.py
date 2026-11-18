# app.py
"""ResumeX - Resume Analyzer (Streamlit front end)."""
import html
import io
import os
import urllib.parse

import streamlit as st

from ai_engine import AIEngineError, analyze_resume_with_gemini
from ml_matcher import ROLE_PROFILES, analyze_offline, load_jobs, rank_jobs
from pdf_parser import extract_text_from_pdf

MAX_FILE_MB = 5
COMPANIES = ["Google", "Amazon", "Microsoft", "Netflix", "Stripe"]
GREEN, AMBER, RED = "#a6e3a1", "#f9e2af", "#f38ba8"

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="ResumeX - Resume Analyzer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 2. STYLING ---
st.markdown(
    """
    <style>
    .block-container { padding-top: 4rem; padding-bottom: 2rem; max-width: 1150px; }
    .card {
        background: #181825; border: 1px solid #313244; border-radius: 14px;
        padding: 22px 24px; margin: 8px 0 18px 0;
    }
    .result-top { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
    .ring-wrap { display: flex; align-items: center; gap: 22px; flex: 1 1 380px; }
    @property --p { syntax: '<number>'; inherits: false; initial-value: 0; }
    .ring {
        --p: 0; flex: none; width: 104px; height: 104px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        background: conic-gradient(var(--c) calc(var(--p) * 1%), #313244 0);
        animation: fill 1.1s ease-out;
    }
    @keyframes fill { from { --p: 0; } }
    .ring-inner {
        width: 84px; height: 84px; border-radius: 50%; background: #11111b;
        display: flex; align-items: center; justify-content: center;
        font-size: 26px; font-weight: 700; color: #cdd6f4;
    }
    .headline { margin: 0; font-size: 22px; font-weight: 650; color: #cdd6f4; }
    .sub { margin: 4px 0 0 0; color: #a6adc8; font-size: 14px; line-height: 1.5; }
    .stat {
        background: #11111b; border: 1px solid #313244; border-radius: 10px;
        padding: 10px 18px; text-align: center; min-width: 96px;
    }
    .stat b { display: block; font-size: 22px; }
    .stat span { font-size: 12px; color: #a6adc8; }
    .tip {
        background: #11111b; border: 1px solid #313244; border-left: 4px solid var(--c);
        border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;
    }
    .tip-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
    .tip-title { color: #cdd6f4; font-weight: 600; font-size: 15px; }
    .tip p { margin: 6px 0 0 0; color: #a6adc8; font-size: 13px; line-height: 1.5; }
    .badge {
        border: 1px solid var(--c); color: var(--c); border-radius: 10px;
        padding: 1px 9px; font-size: 12px; white-space: nowrap;
    }
    .chip {
        display: inline-block; margin: 0 6px 6px 0; padding: 3px 11px;
        border-radius: 12px; font-size: 13px; border: 1px solid var(--c); color: var(--c);
    }
    .stButton > button, .stDownloadButton > button { transition: transform .15s ease; }
    .stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px); }
    @media (prefers-reduced-motion: reduce) {
        .ring { animation: none; }
        .stButton > button, .stDownloadButton > button { transition: none; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- 3. HELPERS ---
def e(value) -> str:
    """Escape text before placing it inside HTML."""
    return html.escape(str(value))


def score_color(score: int) -> str:
    return GREEN if score >= 75 else AMBER if score >= 50 else RED


IMPACT_COLORS = {"High": RED, "Medium": AMBER, "Low": GREEN}


@st.cache_data(show_spinner=False)
def parse_resume(file_bytes: bytes) -> str:
    """Parse once per file instead of on every Streamlit rerun."""
    return extract_text_from_pdf(io.BytesIO(file_bytes))


def build_report(results: dict, role: str, company: str) -> str:
    """Plain-text report for the download button."""
    lines = [
        "RESUME ANALYSIS REPORT",
        f"Target: {role} | Benchmark: {company} | Engine: {results['engine']}",
        f"Match score: {results['match_score']}% ({results['status_headline']})",
        "",
        results["summary"],
        "",
        "Matched skills: " + (", ".join(results["matched_skills"]) or "none"),
        "Skill gaps: " + (", ".join(results["missing_skills"]) or "none"),
        "",
        "Suggestions:",
    ]
    for s in results["suggestions"]:
        lines.append(f"- [{s['impact']}] {s['title']}: {s['description']}")
    lines += ["", "Roadmap: " + results["roadmap_recommendation"]]
    return "\n".join(lines)


def render_chips(items, color):
    if not items:
        st.caption("Nothing to show here.")
        return
    chips = "".join(f'<span class="chip" style="--c:{color}">{e(i)}</span>' for i in items)
    st.markdown(chips, unsafe_allow_html=True)


def render_audit(results: dict, role: str, company: str):
    """Dashboard for a resume audit (same layout for Gemini and Offline)."""
    score = results["match_score"]
    color = score_color(score)
    st.markdown(
        f"""
        <div class="card"><div class="result-top">
          <div class="ring-wrap">
            <div class="ring" style="--p:{score}; --c:{color}">
              <div class="ring-inner">{score}%</div></div>
            <div>
              <p class="headline">{e(results['status_headline'])}</p>
              <p class="sub">{e(results['summary'])}</p>
            </div>
          </div>
          <div class="stat"><b style="color:{GREEN}">{len(results['matched_skills'])}</b><span>Skills found</span></div>
          <div class="stat"><b style="color:{RED}">{len(results['missing_skills'])}</b><span>Skill gaps</span></div>
        </div></div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Analysis engine: {results['engine']}")

    tab_tips, tab_skills, tab_road = st.tabs(
        [f"Suggestions ({len(results['suggestions'])})", "Skills", "Roadmap"]
    )
    with tab_tips:
        if not results["suggestions"]:
            st.success("No major issues found.")
        for s in results["suggestions"]:
            c = IMPACT_COLORS.get(s["impact"], AMBER)
            st.markdown(
                f"""<div class="tip" style="--c:{c}">
                <div class="tip-head"><span class="tip-title">{e(s['title'])}</span>
                <span class="badge">{e(s['impact'])} impact</span></div>
                <p>{e(s['description'])}</p></div>""",
                unsafe_allow_html=True,
            )
    with tab_skills:
        left, right = st.columns(2)
        with left:
            st.markdown("**Found in your resume**")
            render_chips(results["matched_skills"], GREEN)
        with right:
            st.markdown("**Missing or not mentioned**")
            render_chips(results["missing_skills"], RED)
    with tab_road:
        st.info(results["roadmap_recommendation"] or "No roadmap was generated.")

    st.download_button(
        "Download report (.txt)",
        build_report(results, role, company),
        file_name="resume_report.txt",
    )


def render_jobs(ranked, target_field: str):
    """Ranked job recommendations with a comparison chart."""
    st.markdown(f"### Recommended jobs for: {target_field}")
    st.bar_chart(ranked.set_index("title")["score"], horizontal=True, color="#89b4fa")
    st.caption(
        "Score = 70% skill coverage + 30% text similarity (TF-IDF), "
        "+10 if the job title fits your target role."
    )
    for _, row in ranked.iterrows():
        score = row["score"]
        icon = "🟢" if score >= 60 else "🟡" if score >= 35 else "🔴"
        with st.expander(f"{icon} {row['company']} - {row['title']} ({score}%)"):
            st.progress(score / 100)
            c1, c2, c3 = st.columns(3)
            c1.metric("Skill match", f"{row['skill_match']}%")
            c2.metric("Text similarity", f"{row['text_similarity']}%")
            c3.metric("Role fit", "Yes" if row["role_match"] else "No")
            st.write(row["description"])
            if row["missing_skills"]:
                st.warning("Consider adding: " + ", ".join(row["missing_skills"]))
            else:
                st.success("Your resume mentions every skill this job lists.")
            query = urllib.parse.quote(str(row["title"]))
            st.link_button(
                "Search similar roles on LinkedIn",
                f"https://www.linkedin.com/jobs/search/?keywords={query}",
            )


# --- 4. SIDEBAR ---
st.sidebar.header("Settings")
mode = st.sidebar.radio("What do you want to do?", ["Resume audit", "Job recommendations"])
target_field = st.sidebar.selectbox("Target role", list(ROLE_PROFILES))
api_key = st.sidebar.text_input(
    "Gemini API key (optional)",
    type="password",
    value=os.environ.get("GEMINI_API_KEY", ""),
    help="Without a key the audit runs offline with keyword matching.",
)
engine_name = "Gemini" if api_key.strip() else "Offline"
st.sidebar.caption(
    "Audit engine: " + ("Gemini AI" if engine_name == "Gemini" else "offline keyword matching")
    + (" (falls back to offline on errors)" if engine_name == "Gemini" else "")
)
st.sidebar.caption("Job recommendations always run offline.")

# --- 5. HEADER ---
st.title("📄 ResumeX - Resume Analyzer")
st.write(
    "Upload your resume, compare it with a role or a job description, "
    "and see which skills you already show and which you are missing."
)
st.divider()

# --- 6. INPUTS ---
col_upload, col_scope = st.columns(2, gap="large")
resume_text = ""
file_id = None

with col_upload:
    st.subheader("1. Upload your resume")
    uploaded = st.file_uploader("PDF only, up to 5 MB", type=["pdf"])
    if uploaded is not None:
        data = uploaded.getvalue()
        file_id = f"{uploaded.name}-{len(data)}"
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            st.error(f"The file is larger than {MAX_FILE_MB} MB. Upload a smaller PDF.")
        else:
            try:
                resume_text = parse_resume(data)
                if len(resume_text) >= 50:
                    st.success(f"Resume read successfully ({len(resume_text.split())} words).")
                else:
                    resume_text = ""
                    st.warning(
                        "Little or no text was found. This looks like a scanned PDF; "
                        "upload a version with selectable text."
                    )
            except ValueError as err:
                st.error(str(err))

target_company = "Selected role"
job_description = ""
use_profile = True

with col_scope:
    if mode == "Resume audit":
        st.subheader("2. Choose what to compare with")
        source = st.radio(
            "Compare my resume with",
            ["A top tech company's expectations", "A job description I paste"],
            horizontal=True,
        )
        if source.startswith("A top"):
            target_company = st.selectbox("Company", COMPANIES)
            job_description = (
                f"Typical expectations for a {target_field} at {target_company}. "
                f"Core skills: {', '.join(ROLE_PROFILES[target_field])}. "
                "Strong data structures, algorithms and clean coding practices."
            )
        else:
            use_profile = False
            target_company = "Pasted job description"
            job_description = st.text_area(
                "Job description", height=160,
                placeholder="Paste the requirements section of the job posting here...",
            )
    else:
        st.subheader("2. About the job list")
        st.info(
            "Your resume is compared with the sample postings in jobs.csv. "
            "Add rows to that file to compare with more jobs."
        )

st.divider()

# --- 7. RUN ---
st.subheader("3. Results")
label = "Run resume audit" if mode == "Resume audit" else "Find matching jobs"
run = st.button(label, type="primary")

if run:
    st.session_state.pop("audit", None)
    if not resume_text:
        st.error("Upload a readable PDF resume in step 1 first.")
    elif mode == "Resume audit":
        if not use_profile and len(job_description.strip()) < 30:
            st.warning("Paste a longer job description (at least a couple of sentences).")
        else:
            with st.spinner("Analysing your resume..."):
                results = None
                if engine_name == "Gemini":
                    try:
                        results = analyze_resume_with_gemini(
                            api_key, resume_text, target_field,
                            target_company, job_description,
                        )
                    except AIEngineError as err:
                        st.warning(f"{err} Showing the offline analysis instead.")
                if results is None:
                    try:
                        results = analyze_offline(
                            resume_text, target_field, target_company,
                            job_description, use_profile,
                        )
                    except ValueError as err:
                        st.error(str(err))
            if results:
                st.session_state["audit"] = (file_id, results, target_field, target_company)
    else:
        with st.spinner("Matching your resume with the job list..."):
            try:
                ranked = rank_jobs(resume_text, target_field, load_jobs())
                render_jobs(ranked, target_field)
            except ValueError as err:
                st.error(str(err))

# The audit lives in session_state so the download button (which reruns
# the script) does not make the results disappear.
saved = st.session_state.get("audit")
if mode == "Resume audit" and saved and saved[0] == file_id:
    render_audit(saved[1], saved[2], saved[3])
