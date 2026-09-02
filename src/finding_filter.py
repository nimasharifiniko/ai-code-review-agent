"""
Lightweight quality filter for LLM code review findings.

The local 7B model occasionally produces low-value or unreliable
"style" findings — sometimes cosmetic (whitespace, quote style),
sometimes simply factually wrong about the code (e.g. claiming a
redundant assignment that doesn't exist). This filter is a
conservative safety net applied AFTER code_analyzer.py has already
validated and constructed ReviewFinding objects.

Policy:
- BUG, SECURITY, and TESTING findings are preserved by default. This
  filter does not attempt to judge whether they are semantically
  correct — that is the LLM reviewer's responsibility.
- STYLE findings are treated strictly: a style finding is kept ONLY
  when its description/suggestion shows clear evidence of meaningful
  engineering impact (e.g. dangerous duplication, confusing control
  flow, real maintainability risk). Any style finding that does not
  clearly show this is removed, even when the model marks it
  "medium" or higher — severity does not override this policy.

For this MVP, a false-positive style finding is considered more
harmful than an occasional lost weak style recommendation, so doubt
is resolved in favor of removal.

This filter does not call an LLM, does not call GitHub, and does not
access environment variables, logging, or credentials of any kind.
"""

from src.review_schema import ReviewFinding, IssueType

# Phrases that, when present in a STYLE finding's description or
# suggestion, indicate a concrete, material engineering problem
# (rather than a cosmetic or subjective observation). A STYLE finding
# must match at least one of these to survive the filter.
_MEANINGFUL_STYLE_SIGNALS = (
    "duplicat",  # duplicate / duplicated / duplication
    "maintainability",
    "maintenance risk",
    "maintenance burden",
    "confusing control flow",
    "confusing structure",
    "hard to maintain",
    "difficult to maintain",
    "difficult to understand",
    "dangerous pattern",
    "dangerous implementation",
    "misleading",
    "error-prone",
    "increases risk",
    "engineering risk",
    "tightly coupled",
    "deeply nested",
    "hard to test",
)


def filter_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    """
    Return a new list with unreliable/low-value STYLE findings removed.

    BUG, SECURITY, and TESTING findings are kept by default. STYLE
    findings are kept only when they show clear evidence of a
    meaningful engineering impact; all other STYLE findings are
    removed, including ones the model marks as "medium" or higher.

    Ordering is preserved. The input list is never mutated.

    Args:
        findings: Findings already validated by code_analyzer.py.

    Returns:
        list[ReviewFinding]: A new, filtered list.
    """
    return [finding for finding in findings if _should_keep(finding)]


def _should_keep(finding: ReviewFinding) -> bool:
    """
    Decide whether a single finding should be kept.

    BUG, SECURITY, and TESTING findings are always kept — this filter
    does not reason about their correctness. STYLE findings are kept
    only when they show clear evidence of meaningful engineering
    impact (see _has_meaningful_style_impact).
    """
    if finding.type != IssueType.STYLE:
        return True

    return _has_meaningful_style_impact(finding)


def _has_meaningful_style_impact(finding: ReviewFinding) -> bool:
    """
    Check whether a STYLE finding's text shows clear evidence of a
    concrete engineering problem (duplication, confusing control
    flow, dangerous patterns, real maintainability risk), as opposed
    to a cosmetic or subjective observation.

    This is deliberately an allowlist, not a denylist: a STYLE
    finding must positively demonstrate meaningful impact to survive.
    When in doubt, the finding is removed.
    """
    text = f"{finding.description} {finding.suggestion}".lower()

    return any(signal in text for signal in _MEANINGFUL_STYLE_SIGNALS)
