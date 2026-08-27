"""
Structured data contract for code review findings.

This module defines the schema used to represent a single issue
detected during automated code review. It is intentionally limited
to data representation only — no GitHub API logic, no LLM calls,
no formatting, and no CLI logic belong here.

Downstream consumers of this schema:
- The LLM output layer (parses raw model output into ReviewFinding instances)
- Validation / processing logic
- The comment/review formatter
- The GitHub PR comment/review publisher
"""

from dataclasses import dataclass
from enum import Enum


class IssueType(str, Enum):
    """Category of a detected code issue."""
    BUG = "bug"
    SECURITY = "security"
    STYLE = "style"
    TESTING = "testing"


class Severity(str, Enum):
    """Relative severity of a detected code issue."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ReviewFinding:
    """
    A single code review finding.

    Represents one issue detected in a pull request diff, at a
    specific file/line location, with enough context to be shown
    to a human reviewer as an actionable comment.
    """

    file: str
    line: int
    type: IssueType
    severity: Severity
    description: str
    suggestion: str
