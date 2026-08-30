"""
Markdown formatter for code review findings.

Converts a list of ReviewFinding objects into a readable Markdown
string suitable for posting as a GitHub Pull Request comment.

This module operates only on the ReviewFinding objects it receives —
it never touches environment variables, external APIs, or credentials.
"""

from src.review_schema import ReviewFinding, Severity

_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}

_SEVERITY_ICONS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
}

_SEVERITY_LABELS = {
    Severity.CRITICAL: "Critical",
    Severity.HIGH: "High",
    Severity.MEDIUM: "Medium",
    Severity.LOW: "Low",
}

_TYPE_LABELS = {
    "bug": "Bug",
    "security": "Security",
    "style": "Style",
    "testing": "Testing",
}


def format_findings(findings: list[ReviewFinding]) -> str:
    """
    Format a list of review findings as a Markdown report.

    Args:
        findings: Findings to format. Not mutated.

    Returns:
        str: A Markdown-formatted report, ready to post as a
             GitHub Pull Request comment.
    """
    if not findings:
        return "## 🤖 AI Code Review\n\n✅ No issues found in the reviewed changes."

    sorted_findings = _sort_by_severity(findings)

    sections = [_format_single_finding(finding) for finding in sorted_findings]

    return "## 🤖 AI Code Review\n\n" + "\n\n".join(sections)


def _sort_by_severity(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    """
    Return a new list sorted by severity (critical first, low last).

    Findings with equal severity keep their original relative order
    (stable sort). The input list is never mutated.
    """
    return sorted(findings, key=lambda f: _SEVERITY_ORDER[f.severity])


def _format_single_finding(finding: ReviewFinding) -> str:
    """Format a single finding as a Markdown section."""
    icon = _SEVERITY_ICONS[finding.severity]
    severity_label = _SEVERITY_LABELS[finding.severity]
    type_label = _TYPE_LABELS[finding.type.value]

    return (
        f"### {icon} {severity_label} — {type_label}\n\n"
        f"**`{finding.file}:{finding.line}`**\n\n"
        f"{finding.description}\n\n"
        f"**Suggestion:** {finding.suggestion}"
    )
