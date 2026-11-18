# ai_engine.py
"""Resume analysis using the Gemini API.

If Gemini cannot be used, this module raises AIEngineError with a clear
message. It never returns invented data; the app decides what to do next.
"""
import json
import time

MODELS_TO_TRY = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]
MAX_RESUME_CHARS = 15000  # keeps the prompt within a sensible size


class AIEngineError(Exception):
    """Raised when the Gemini analysis could not be completed."""


def build_prompt(resume: str, role: str, company: str, job_reqs: str) -> str:
    return f"""
You are an expert technical recruiter and resume reviewer.
Analyze the resume below against the target role and job description.
Base every statement ONLY on the resume text. Do not invent skills or
experience that the resume does not mention.

TARGET ROLE: {role}
BENCHMARK: {company}
JOB DESCRIPTION / REQUIREMENTS:
{job_reqs}

RESUME TEXT:
{resume[:MAX_RESUME_CHARS]}

Respond strictly as valid JSON with these keys:
"match_score": integer 0-100
"status_headline": short string
"summary": brief paragraph explaining the overall fit
"matched_skills": list of strings
"missing_skills": list of strings
"suggestions": list of objects with "title", "impact" ("High" or "Medium"), "description"
"roadmap_recommendation": string
"""


def validate_result(data) -> dict:
    """Check the model's JSON and return a clean, predictable dict."""
    if not isinstance(data, dict):
        raise AIEngineError("Gemini returned an unexpected response format.")
    try:
        score = int(data["match_score"])
    except (KeyError, TypeError, ValueError):
        raise AIEngineError("Gemini's response had no valid match score.")

    def as_list(key):
        value = data.get(key, [])
        return [str(v) for v in value] if isinstance(value, list) else []

    suggestions = []
    for item in data.get("suggestions", []) if isinstance(
            data.get("suggestions"), list) else []:
        if not isinstance(item, dict):
            continue
        impact = str(item.get("impact", "Medium")).title()
        suggestions.append({
            "title": str(item.get("title", "")),
            "impact": impact if impact in ("High", "Medium", "Low") else "Medium",
            "description": str(item.get("description", "")),
        })

    return {
        "engine": "Gemini",
        "match_score": max(0, min(100, score)),
        "status_headline": str(data.get("status_headline", "")),
        "summary": str(data.get("summary", "")),
        "matched_skills": as_list("matched_skills"),
        "missing_skills": as_list("missing_skills"),
        "suggestions": suggestions,
        "roadmap_recommendation": str(data.get("roadmap_recommendation", "")),
    }


def analyze_resume_with_gemini(
    api_key: str, resume: str, role: str, company: str, job_reqs: str
) -> dict:
    """Analyse the resume with Gemini. Raises AIEngineError on failure."""
    if not api_key or not api_key.strip():
        raise AIEngineError("No Gemini API key was provided.")

    try:  # imported here so the offline mode works without this package
        from google import genai
        from google.genai import types
    except ImportError:
        raise AIEngineError(
            "The google-genai package is not installed (pip install google-genai)."
        )

    client = genai.Client(api_key=api_key.strip())
    prompt = build_prompt(resume, role, company, job_reqs)
    last_error = None

    for model_name in MODELS_TO_TRY:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                )
                text = (response.text or "").strip()
                text = text.removeprefix("```json").removesuffix("```").strip()
                return validate_result(json.loads(text))
            except json.JSONDecodeError as exc:
                last_error = exc  # malformed JSON: try again
            except AIEngineError as exc:
                last_error = exc
            except Exception as exc:
                code = getattr(exc, "code", None)
                if code in (400, 401, 403):  # retrying cannot fix a bad key
                    raise AIEngineError(
                        "Gemini rejected the request. Check that your API key is valid."
                    ) from exc
                last_error = exc
                if code == 404:  # this model name is unavailable: next model
                    break
            if attempt == 0:
                time.sleep(1.5)

    raise AIEngineError(
        f"Gemini is unavailable right now ({type(last_error).__name__})."
    )
