"""
LLM code analysis engine.

Sends a Pull Request diff to a locally running LLM (via Ollama) and
returns structured, validated ReviewFinding objects. The caller does
not need to know which LLM provider is used — analyze_diff() is the
only public entry point.

Zero-cost by default: the local Ollama provider is used unless a
different LLM_PROVIDER is explicitly configured.
"""

import json
import logging
import os

import requests
from dotenv import load_dotenv

from src.review_schema import ReviewFinding, IssueType, Severity
from src.prompts import SYSTEM_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)

_VALID_TYPES = {t.value for t in IssueType}
_VALID_SEVERITIES = {s.value for s in Severity}
_REQUIRED_FIELDS = {"file", "line", "type",
                    "severity", "description", "suggestion"}

# JSON schema for Ollama's structured output ("format" field).
# Mirrors the ReviewFinding contract in src/review_schema.py.
_FINDINGS_JSON_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "line": {"type": "integer"},
            "type": {"type": "string", "enum": ["bug", "security", "style", "testing"]},
            "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            "description": {"type": "string"},
            "suggestion": {"type": "string"},
        },
        "required": ["file", "line", "type", "severity", "description", "suggestion"],
        "additionalProperties": False,
    },
}


class CodeAnalysisError(Exception):
    """Raised when diff analysis fails for any reason (config, network, or validation)."""


def analyze_diff(diff: str) -> list[ReviewFinding]:
    """
    Analyze a Pull Request diff and return structured review findings.

    Args:
        diff: The diff/patch text to review. Can come from GitHub,
              a manual test, or any other source — this function has
              no knowledge of where it came from.

    Returns:
        list[ReviewFinding]: Validated findings. An empty list is a
                              valid result meaning no issues were found.

    Raises:
        CodeAnalysisError: On invalid input, misconfiguration, provider
                            failure, or malformed/invalid model output.
    """
    if not diff or not diff.strip():
        raise CodeAnalysisError("Diff cannot be empty.")

    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

    if provider == "ollama":
        raw_content = _call_ollama(diff)
    else:
        raise CodeAnalysisError(f"Unsupported LLM_PROVIDER: '{provider}'.")

    findings_data = _parse_json_content(raw_content)
    findings = _validate_findings(findings_data)

    logger.info("LLM analysis complete: provider=%s findings=%d",
                provider, len(findings))

    return findings


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------

def _build_user_message(diff: str) -> str:
    """Build the user message instructing the model how to respond."""
    return (
        "The following is a Pull Request diff. Review it according to your "
        "instructions.\n\n"
        "Return ONLY a JSON array of findings. Do not return Markdown. "
        "Do not include any explanation outside the JSON array.\n\n"
        "DIFF START\n"
        f"{diff}\n"
        "DIFF END"
    )


def _call_ollama(diff: str) -> str:
    """
    Send the diff to a local Ollama instance and return the raw
    assistant message content (expected to be a JSON string).

    Raises:
        CodeAnalysisError: On configuration errors, network failures,
                            or an unusable response shape.
    """
    base_url = _get_ollama_base_url()
    model = _get_ollama_model()
    timeout = _get_ollama_timeout()

    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(diff)},
        ],
        "stream": False,
        "format": _FINDINGS_JSON_SCHEMA,
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.exceptions.Timeout as exc:
        raise CodeAnalysisError("Ollama request timed out.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise CodeAnalysisError("Ollama server is unavailable.") from exc
    except requests.exceptions.RequestException as exc:
        raise CodeAnalysisError("Ollama request failed.") from exc

    if not response.ok:
        raise CodeAnalysisError(
            f"Ollama server returned a non-success status: {response.status_code}."
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise CodeAnalysisError("Model response was not valid JSON.") from exc

    if not isinstance(data, dict) or "message" not in data:
        raise CodeAnalysisError(
            "Ollama response is missing the 'message' field.")

    message = data["message"]
    if not isinstance(message, dict) or "content" not in message:
        raise CodeAnalysisError(
            "Ollama response message is missing 'content'.")

    content = message["content"]
    if not isinstance(content, str) or not content.strip():
        raise CodeAnalysisError("Ollama response content is empty.")

    return content


def _get_ollama_base_url() -> str:
    """Read and normalize OLLAMA_BASE_URL (trailing slash removed)."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    if not base_url:
        raise CodeAnalysisError("OLLAMA_BASE_URL cannot be empty.")
    return base_url.rstrip("/")


def _get_ollama_model() -> str:
    """Read OLLAMA_MODEL. Required — no arbitrary default is chosen."""
    model = os.getenv("OLLAMA_MODEL", "").strip()
    if not model:
        raise CodeAnalysisError(
            "OLLAMA_MODEL is required but not set. Please configure a local model name."
        )
    return model


def _get_ollama_timeout() -> int:
    """Read and validate OLLAMA_TIMEOUT as a positive integer."""
    raw_timeout = os.getenv("OLLAMA_TIMEOUT", "60").strip()

    try:
        timeout = int(raw_timeout)
    except ValueError as exc:
        raise CodeAnalysisError(
            f"OLLAMA_TIMEOUT must be a positive integer, got: '{raw_timeout}'."
        ) from exc

    if timeout <= 0:
        raise CodeAnalysisError(
            f"OLLAMA_TIMEOUT must be a positive integer, got: {timeout}."
        )

    return timeout


# ---------------------------------------------------------------------------
# Response parsing and validation
# ---------------------------------------------------------------------------

def _parse_json_content(content: str) -> object:
    """Parse the assistant's raw content string as JSON."""
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise CodeAnalysisError("Model response was not valid JSON.") from exc


def _validate_findings(data: object) -> list[ReviewFinding]:
    """
    Validate parsed JSON data and convert it into ReviewFinding objects.

    Raises:
        CodeAnalysisError: If the top-level structure or any individual
                            finding is invalid. Nothing is silently dropped.
    """
    if not isinstance(data, list):
        raise CodeAnalysisError(
            "Model output must be a JSON array of findings.")

    findings: list[ReviewFinding] = []

    for index, item in enumerate(data):
        findings.append(_validate_single_finding(item, index))

    return findings


def _validate_single_finding(item: object, index: int) -> ReviewFinding:
    """Validate a single finding object and convert it into a ReviewFinding."""
    if not isinstance(item, dict):
        raise CodeAnalysisError(
            f"Finding at index {index} is not a JSON object.")

    missing = _REQUIRED_FIELDS - item.keys()
    if missing:
        raise CodeAnalysisError(
            f"Finding at index {index} is missing required field(s): {sorted(missing)}."
        )

    file_value = item["file"]
    if not isinstance(file_value, str) or not file_value.strip():
        raise CodeAnalysisError(
            f"Finding at index {index} has an invalid 'file' value.")

    line_value = item["line"]
    if not isinstance(line_value, int) or isinstance(line_value, bool) or line_value < 0:
        raise CodeAnalysisError(
            f"Finding at index {index} has an invalid 'line' value.")

    type_value = item["type"]
    if type_value not in _VALID_TYPES:
        raise CodeAnalysisError(
            f"Finding at index {index} has an invalid 'type' value: '{type_value}'."
        )

    severity_value = item["severity"]
    if severity_value not in _VALID_SEVERITIES:
        raise CodeAnalysisError(
            f"Finding at index {index} has an invalid 'severity' value: '{severity_value}'."
        )

    description_value = item["description"]
    if not isinstance(description_value, str) or not description_value.strip():
        raise CodeAnalysisError(
            f"Finding at index {index} has an invalid 'description' value.")

    suggestion_value = item["suggestion"]
    if not isinstance(suggestion_value, str) or not suggestion_value.strip():
        raise CodeAnalysisError(
            f"Finding at index {index} has an invalid 'suggestion' value.")

    return ReviewFinding(
        file=file_value,
        line=line_value,
        type=IssueType(type_value),
        severity=Severity(severity_value),
        description=description_value,
        suggestion=suggestion_value,
    )
