"""Developer — REAL implementation. Owner: Member 3.

The Developer is called MULTIPLE times: first to write v1, then again after
the Reviewer or Tester sends feedback (the collaboration loop worth marks).
Output is strict JSON `{"files": {"path": "content", ...}}`, parsed with
json.loads (one retry on a parse failure), then syntax-checked before being
handed back to the supervisor.
"""
import json
import re

from src import config
from src.agents.base import call_llm, msg
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry
from src.tools.code_exec import syntax_check

AGENT = "developer"

SYSTEM_PROMPT = """You are a senior developer on an AI software team.
Given a requirements specification and an architecture document, implement
the project as working files — follow the architecture doc's "Project type"
exactly, it already decided this for you:

- STATIC FRONTEND: write ONLY .html/.css/.js files — no Python backend, no
  server, no Flask. Still include exactly one Python test file (tests/ or
  test_*.py) using pytest that reads the HTML file(s) as plain text (no
  server needed) and asserts the key elements/structure from the
  requirements are present. Make it visually polished, not raw unstyled
  HTML — prefer Tailwind CSS via CDN
  (`<script src="https://cdn.tailwindcss.com"></script>` in `<head>`, then
  Tailwind utility classes) since it always renders correctly with zero
  risk of a broken stylesheet link. If you write a separate .css file
  instead, every HTML file MUST `<link rel="stylesheet" href="...">` it
  using the EXACT same path you used as its key in "files", and the CSS
  must contain real, substantial rules (layout, color, spacing,
  typography) — not a handful of trivial ones.
- FULL-STACK: implement in Python, using ONLY the standard library — the
  test sandbox has no internet access and installs no pip packages, only
  what's already on the machine running this app (stdlib + pytest). Never
  import Flask, FastAPI, Django, requests, SQLAlchemy, etc. —
  `http.server`/`wsgiref` for HTTP, `sqlite3` for persistence against a
  real on-disk database file (per the architecture doc's schema), never an
  in-memory dict/list. Tests should use a temporary db file (e.g. via
  tempfile) so they don't collide with each other or leave state behind.

Respond with ONLY strict JSON of the form:
{"files": {"path/to/file": "<full file content>", ...}}

Rules:
- No prose, no markdown code fences — the response must be valid JSON and
  nothing else.
- Include exactly one test file (tests/ or test_*.py) using pytest.
- If given "reviewer feedback" or a "failing test report", fix ONLY the
  reported issues — do not rewrite unrelated code."""


def _extract_json(text: str) -> str:
    """Strip markdown code fences if the model added them anyway."""
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    return fence.group(1) if fence else text


def _parse_files(text: str) -> dict:
    candidate = _extract_json(text)
    start = candidate.find("{")
    if start == -1:
        raise ValueError("no JSON object found in the response")
    # raw_decode parses just the first complete JSON value and ignores
    # anything after it — models occasionally add trailing prose/duplicate
    # content after an otherwise-valid {"files": ...} object, which
    # json.loads() would reject wholesale as "Extra data".
    payload, _ = json.JSONDecoder().raw_decode(candidate, start)
    files = payload["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("'files' must be a non-empty object")
    return files


_CSS_CDN_PATTERN = re.compile(
    r"cdn\.tailwindcss\.com|cdn\.jsdelivr\.net/npm/bootstrap|unpkg\.com/[^\"'\s]*\.css|fonts\.googleapis\.com",
    re.IGNORECASE,
)
_INLINE_STYLE_PATTERN = re.compile(r"<style[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
_LINK_HREF_PATTERN = re.compile(r'<link[^>]+href=["\']([^"\']+\.css)["\']', re.IGNORECASE)
_HTML_CLASS_ATTR_PATTERN = re.compile(r'class=["\']([^"\']+)["\']', re.IGNORECASE)
_CSS_CLASS_SELECTOR_PATTERN = re.compile(r"\.(-?[a-zA-Z_][a-zA-Z0-9_-]*)")
# Classes from external icon-font CDNs (Font Awesome, Bootstrap Icons, etc.)
# are styled by that CDN's own stylesheet, not the project's CSS — excluded
# from coverage so they can't cause a false positive.
_ICON_CLASS_PREFIXES = ("fa-", "fas", "far", "fab", "fal", "fad", "bi-", "material-icons", "glyphicon", "icon-")


def _class_tokens(html: str) -> set:
    tokens = set()
    for attr_value in _HTML_CLASS_ATTR_PATTERN.findall(html):
        tokens.update(attr_value.split())
    return {t for t in tokens if not t.startswith(_ICON_CLASS_PREFIXES)}


def _check_frontend_styling(files: dict) -> list:
    """Guard against the silent "raw unstyled HTML" failure mode. Two
    mechanical (non-LLM) checks, wired into the same retry loop as
    syntax_check:
    1. A linked .css file that doesn't exist among the generated files
       (typo/path mismatch), or no styling reference at all.
    2. The much sneakier failure: a real, correctly-linked CSS file whose
       selectors don't actually match the HTML's class names (e.g. CSS
       defines `.nav-item` while the HTML uses `.nav-link`) — the file
       "exists", but nothing it contains ever applies. Flags when fewer
       than 30% of the HTML's classes have any matching CSS rule."""
    html_files = {p: c for p, c in files.items() if p.lower().endswith(".html")}
    if not html_files:
        return []
    css_paths = {p for p in files if p.lower().endswith(".css")}
    problems = []
    for path, content in html_files.items():
        linked = _LINK_HREF_PATTERN.findall(content)
        matched_css_paths = {
            css_path
            for href in linked
            for css_path in css_paths
            if href.lstrip("./") in (css_path, css_path.split("/")[-1])
        }
        has_cdn = bool(_CSS_CDN_PATTERN.search(content))
        inline_css = "\n".join(_INLINE_STYLE_PATTERN.findall(content))

        if linked and not matched_css_paths and not has_cdn:
            problems.append(
                f"{path}: <link> references {linked} but no matching file exists among "
                f"{sorted(css_paths) or 'the generated .css files (none were generated)'} "
                "— the page will render unstyled."
            )
            continue
        if not linked and not inline_css.strip() and not has_cdn:
            problems.append(
                f"{path}: no <link>ed stylesheet, inline <style> block, or CSS-framework CDN "
                "tag found — this will render as raw unstyled HTML."
            )
            continue

        # CDN frameworks (Tailwind etc.) style via utility classes we can't
        # verify without downloading them — skip the coverage check there.
        if has_cdn:
            continue

        css_text = inline_css + "\n" + "\n".join(files[p] for p in matched_css_paths)
        html_classes = _class_tokens(content)
        if not html_classes:
            continue
        css_classes = set(_CSS_CLASS_SELECTOR_PATTERN.findall(css_text))
        covered = html_classes & css_classes
        if len(covered) / len(html_classes) < 0.3:
            problems.append(
                f"{path}: its CSS is linked correctly but only {len(covered)}/{len(html_classes)} "
                f"of its HTML classes have a matching CSS rule (e.g. unmatched: "
                f"{sorted(html_classes - covered)[:8]}) — the class names in the HTML and CSS "
                "don't line up, so the page will render mostly unstyled. Make sure every class "
                "used in the HTML has a corresponding selector in the CSS."
            )
    return problems


def _generate_files(agent_name: str, user_prompt: str) -> tuple[dict, dict]:
    """Call the LLM and parse its JSON response, retrying once on failure."""
    text, usage = call_llm(agent_name, SYSTEM_PROMPT, user_prompt)
    try:
        return _parse_files(text), usage
    except (json.JSONDecodeError, KeyError, ValueError) as error:
        log_entry(agent_name, "WARNING", f"Developer JSON parse failed, retrying once: {error}")
        retry_prompt = (
            user_prompt
            + f"\n\nYour previous response was not valid JSON ({error}). "
            "Respond again with ONLY the JSON object, no other text."
        )
        text2, usage2 = call_llm(agent_name, SYSTEM_PROMPT, retry_prompt)
        files = _parse_files(text2)  # let a second failure raise — supervisor logs it
        merged_usage = {
            AGENT: {
                "input_tokens": usage.get(AGENT, {}).get("input_tokens", 0)
                + usage2.get(AGENT, {}).get("input_tokens", 0),
                "output_tokens": usage.get(AGENT, {}).get("output_tokens", 0)
                + usage2.get(AGENT, {}).get("output_tokens", 0),
                "cost_usd": usage.get(AGENT, {}).get("cost_usd", 0)
                + usage2.get(AGENT, {}).get("cost_usd", 0),
            }
        }
        return files, merged_usage


def _format_code(code_files: dict) -> str:
    return "\n\n".join(f"### {path}\n```\n{content}\n```" for path, content in code_files.items())


def developer_node(state: ProjectState) -> dict:
    revision = state.get("revision_count", 0)
    modifying = bool(state.get("modification_pending"))
    review_rework = bool(state.get("review_feedback")) and not state.get("review_approved", False)
    test_rework = bool(state.get("test_report")) and not state.get("tests_passed", False)
    is_rework = modifying or review_rework or test_rework

    if config.MOCK_MODE:
        files = canned_outputs.CODE_V2 if is_rework else canned_outputs.CODE_V1
        usage = {}
        note = (
            f"Applied the requested modification (mock mode)."
            if modifying
            else f"Rework round {revision + 1}: fixed all issues from the code review (mock mode)."
            if is_rework
            else "Implemented v1 from the architecture (mock mode)."
        )
    else:
        if modifying:
            # A post-finish modification request: work from the EXISTING
            # code, not from scratch — everything not mentioned must stay
            # exactly as it is.
            user_prompt = (
                f"Existing code files:\n{_format_code(state.get('code_files', {}))}\n\n"
                "The user has requested this change to the project above — apply ONLY this "
                "change and leave everything else exactly as it is:\n"
                f"{state.get('modification_request', '')}"
            )
        else:
            user_prompt = (
                f"Requirements:\n{state.get('requirements_doc', '')}\n\n"
                f"Architecture:\n{state.get('architecture_doc', '')}"
            )
            if review_rework:
                user_prompt += f"\n\nReviewer feedback to fix:\n{state['review_feedback']}"
            if test_rework:
                user_prompt += f"\n\nFailing test report to fix:\n{state['test_report']}"

        files, usage = _generate_files(AGENT, user_prompt)
        errors = syntax_check(files) + _check_frontend_styling(files)
        if errors:
            log_entry(AGENT, "WARNING", f"Issues in generated code, retrying once: {errors}")
            retry_prompt = user_prompt + "\n\nYour code had issues:\n" + "\n".join(errors)
            try:
                files, extra_usage = _generate_files(AGENT, retry_prompt)
                for key in ("input_tokens", "output_tokens", "cost_usd"):
                    usage.setdefault(AGENT, {})[key] = usage.get(AGENT, {}).get(
                        key, 0
                    ) + extra_usage.get(AGENT, {}).get(key, 0)
            except (json.JSONDecodeError, KeyError, ValueError) as error:
                # The fix-up retry itself failed to produce parseable JSON
                # (e.g. a long regeneration ran past the model's output
                # limit). Ship the original, already-valid `files` instead
                # of crashing the whole pipeline run over an imperfect —
                # but working — first draft; the Reviewer/Tester loop still
                # gets a chance to catch what's left.
                log_entry(AGENT, "WARNING", f"Issue-fix retry also failed to parse, keeping v1: {error}")

        note = (
            f"Applied the requested modification ({len(files)} files)."
            if modifying
            else f"Rework round {revision + 1}: fixed the reported issues ({len(files)} files)."
            if is_rework
            else f"Implemented v1 from the architecture ({len(files)} files)."
        )

    return {
        "code_files": files,
        "modification_pending": False,  # this round's change has been applied
        # Rework resets review + tests so the Reviewer/Tester run again:
        "review_feedback": "",
        "review_approved": False,
        "test_report": "",
        "tests_passed": False,
        "revision_count": revision + (1 if is_rework else 0),
        "agent_messages": [msg(AGENT, "supervisor", note)],
        "logs": [log_entry(AGENT, "INFO", note)],
        "token_usage": usage,
    }
