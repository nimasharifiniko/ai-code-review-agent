"""
Manual end-to-end evaluation script for the local LLM code review pipeline.

Runs three controlled diffs through the REAL Ollama-backed pipeline
(analyze_diff -> filter_findings -> format_findings) — no mocking,
no fake responses.

This is a temporary evaluation tool, not an automated test suite.
Run directly with:

    python -m src.test_code_review
"""

from src.code_analyzer import analyze_diff
from src.finding_filter import filter_findings
from src.formatter import format_findings


# ---------------------------------------------------------------------------
# Test diffs
# ---------------------------------------------------------------------------

BUG_DIFF = """\
diff --git a/src/math_utils.py b/src/math_utils.py
index e69de29..f2c1a3b 100644
--- a/src/math_utils.py
+++ b/src/math_utils.py
@@ -1,3 +1,8 @@
+def divide(a, b):
+    \"\"\"Divide a by b.\"\"\"
+    return a / b
+
+def average(values):
+    total = sum(values)
+    return divide(total, len(values))
"""

SECURITY_DIFF = """\
diff --git a/src/api_client.py b/src/api_client.py
index e69de29..a1b2c3d 100644
--- a/src/api_client.py
+++ b/src/api_client.py
@@ -1,3 +1,9 @@
+import requests
+
+API_KEY = "sk-test-example-not-real"
+
+def fetch_data(endpoint):
+    headers = {"Authorization": f"Bearer {API_KEY}"}
+    response = requests.get(endpoint, headers=headers)
+    return response.json()
"""

CLEAN_DIFF = """\
diff --git a/src/string_utils.py b/src/string_utils.py
index e69de29..b4d5e6f 100644
--- a/src/string_utils.py
+++ b/src/string_utils.py
@@ -1,3 +1,10 @@
+def slugify(text: str) -> str:
+    \"\"\"Convert text into a URL-friendly slug.\"\"\"
+    if not text:
+        return ""
+    cleaned = text.strip().lower()
+    cleaned = "-".join(cleaned.split())
+    return cleaned
"""


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _print_header(title: str) -> None:
    print("=" * 60)
    print(title)
    print("=" * 60)


def _print_findings(label: str, findings: list) -> None:
    print(f"{label}: {len(findings)}\n")
    for finding in findings:
        print(f"  file:        {finding.file}")
        print(f"  line:        {finding.line}")
        print(f"  type:        {finding.type.value}")
        print(f"  severity:    {finding.severity.value}")
        print(f"  description: {finding.description}")
        print(f"  suggestion:  {finding.suggestion}")
        print()


def _run_test_case(title: str, diff: str) -> tuple[int, int]:
    _print_header(title)

    raw_findings = analyze_diff(diff)
    _print_findings("Raw findings", raw_findings)

    filtered_findings = filter_findings(raw_findings)
    _print_findings("Filtered findings", filtered_findings)

    markdown = format_findings(filtered_findings)
    print(markdown)
    print()

    return len(raw_findings), len(filtered_findings)


def main() -> None:
    bug_raw, bug_filtered = _run_test_case(
        "TEST 1 — INTENTIONAL BUG", BUG_DIFF)
    security_raw, security_filtered = _run_test_case(
        "TEST 2 — SECURITY ISSUE", SECURITY_DIFF)
    clean_raw, clean_filtered = _run_test_case(
        "TEST 3 — CLEAN CODE", CLEAN_DIFF)

    _print_header("SUMMARY")
    print("Bug test:")
    print(f"  Raw findings: {bug_raw}")
    print(f"  Filtered findings: {bug_filtered}")
    print()
    print("Security test:")
    print(f"  Raw findings: {security_raw}")
    print(f"  Filtered findings: {security_filtered}")
    print()
    print("Clean test:")
    print(f"  Raw findings: {clean_raw}")
    print(f"  Filtered findings: {clean_filtered}")


if __name__ == "__main__":
    main()
