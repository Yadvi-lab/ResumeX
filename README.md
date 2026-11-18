# ResumeX - Resume Analyzer

A Streamlit web app that reads a PDF resume, finds the technical skills it mentions, and compares them with a target role or a job description. It shows which skills are present, which are missing, and how to improve the resume. It can also rank sample job postings against the resume.

Built as an M.Sc. (Data Science) minor project using Python.
**[View Live App on Streamlit] (https://resumex-tnyg8obiurjuanjm3vhjen.streamlit.app/)**

## Features

- **Resume audit:** match score, skills found, skill gaps, suggestions, and a short roadmap.
- **Two ways to compare:** a top tech company's expected skills for a role, or a job description you paste.
- **Job recommendations:** ranks the postings in `jobs.csv` by how well your resume fits.
- **Two analysis engines:**
  - *Offline* (default): keyword matching, no internet or API key needed.
  - *Gemini AI* (optional): richer analysis. If it fails, the app shows the error and uses the offline engine. It never shows invented results.
- **Resume checks:** email, standard sections, measurable results, and length.
- **Downloadable report** (.txt) of the audit.

## Tech stack

| Purpose | Library |
|---|---|
| Web interface | Streamlit |
| PDF text extraction | pdfplumber |
| Tables and data | pandas |
| Text similarity (TF-IDF, cosine) | scikit-learn |
| AI analysis (optional) | google-genai |

## Project structure

```
resume_analyzer/
├── app.py              # Streamlit interface; connects everything
├── pdf_parser.py       # Reads text from the uploaded PDF
├── ml_matcher.py       # Skill detection, job ranking, offline audit
├── ai_engine.py        # Gemini analysis and validation of its output
├── jobs.csv            # Sample job postings
├── requirements.txt    # Python dependencies
└── .streamlit/
    └── config.toml     # Dark theme settings
```

## Installation

Requires Python 3.9 or newer.

```bash
pip install -r requirements.txt
```

## Running the app

```bash
streamlit run app.py
```

The app opens in your browser at `http://localhost:8501`.

**Optional - enable Gemini:** paste a Gemini API key into the sidebar, or set it before starting:

```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="your-key"
# macOS / Linux
export GEMINI_API_KEY="your-key"
```

## How to use

1. Choose **Resume audit** or **Job recommendations** in the sidebar and pick a target role.
2. Upload your resume as a PDF (up to 5 MB, text-based, not a scan).
3. For an audit, choose a company benchmark or paste a job description.
4. Click the run button and read the results.

## How scoring works

- **Skill detection:** about 30 skills are matched as whole words, so "Java" is not found inside "JavaScript".
- **Audit score (offline):** skills found / skills expected x 100.
- **Job score:** 70% skill coverage + 30% TF-IDF text similarity, plus 10 if the job title fits the chosen role (maximum 100).

## Customising

- **Add jobs:** add rows to `jobs.csv` with the columns `title`, `company`, `description`, `url`.
- **Add skills or roles:** edit the `SKILLS` and `ROLE_PROFILES` dictionaries in `ml_matcher.py`.

## Limitations

- Only about 30 skills are recognised.
- The offline audit checks which skills are written down, not how well you know them.
- Scanned (image) PDFs cannot be read because there is no OCR.
- `jobs.csv` is a small sample, so recommendations are a demonstration.
- Gemini results can vary between runs and need internet access and an API key.

## Future scope

More skills and jobs, DOCX support, OCR for scanned resumes, meaning-based matching with embeddings, and live job data from an API.
