"""
Application-level orchestration layer for the AI Code Review Agent.

This module coordinates the existing review pipeline components — it
does not implement GitHub communication, LLM analysis, filtering, or
formatting itself. Those responsibilities remain in their respective
modules; this file only wires them together into a single call:

    Pull Request (owner, repo, pull_number)
        -> list[ChangedFile] (github_client.py)
        -> diff text (built here from ChangedFile data)
        -> findings (code_analyzer.py)
        -> filtered findings (finding_filter.py)
        -> Markdown (formatter.py)
"""

import logging

from src.config import get_github_token
from src.github_client import GitHubClient, ChangedFile
from src.code_analyzer import analyze_diff
from src.finding_filter import filter_findings
from src.formatter import format_findings

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Raised when the review orchestration fails at any stage."""


def run_review(owner: str, repo: str, pull_number: int) -> str:
    """
    Run the full code review pipeline for a single Pull Request and
    return a Markdown report.

    Args:
        owner:       Repository owner (user or organization).
        repo:        Repository name.
        pull_number: Pull Request number.

    Returns:
        str: Markdown-formatted review report, ready to be posted
             as a Pull Request comment.

    Raises:
        AgentError: If any stage of the pipeline fails (configuration,
                    GitHub access, diff preparation, LLM analysis,
                    filtering, or formatting).
    """
    changed_files = _get_changed_files(owner, repo, pull_number)

    if not changed_files:
        logger.info(
            "No changed files for %s/%s#%d — skipping analysis.", owner, repo, pull_number)
        return format_findings([])

    diff_text = _build_diff_text(changed_files)

    findings = _analyze(diff_text)
    filtered_findings = _filter(findings)
    markdown = _format(filtered_findings)

    logger.info(
        "Review complete for %s/%s#%d: %d changed file(s), %d finding(s) after filtering.",
        owner, repo, pull_number, len(changed_files), len(filtered_findings),
    )

    return markdown


def _get_changed_files(owner: str, repo: str, pull_number: int) -> list[ChangedFile]:
    """Retrieve the Pull Request's changed files via the GitHub client."""
    try:
        token = get_github_token()
    except Exception as exc:
        raise AgentError(
            "Failed to load GitHub authentication configuration.") from exc

    try:
        client = GitHubClient(token=token)
        return client.get_pull_request_diff(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
        )
    except Exception as exc:
        raise AgentError(
            f"Failed to retrieve Pull Request files for {owner}/{repo}#{pull_number}.") from exc


def _build_diff_text(changed_files: list[ChangedFile]) -> str:
    """
    Build a single readable diff string from the changed files
    returned by the GitHub API.

    Each file's filename and status are always included. The patch
    is included when available; if a file has no patch (which the
    GitHub API can omit in some cases), the file is still listed
    with its filename and status, without inventing patch content.
    """
    try:
        sections = [_format_changed_file(changed_file)
                    for changed_file in changed_files]
        return "\n\n".join(sections)
    except Exception as exc:
        raise AgentError(
            "Failed to prepare diff text from changed files.") from exc


def _format_changed_file(changed_file: ChangedFile) -> str:
    """Format a single ChangedFile as a diff-like text section."""
    header = (
        f"diff --git a/{changed_file.filename} b/{changed_file.filename}\n"
        f"status: {changed_file.status}"
    )

    if changed_file.patch:
        return f"{header}\n\n{changed_file.patch}"

    return header


def _analyze(diff: str) -> list:
    """Run LLM analysis on the diff text."""
    try:
        return analyze_diff(diff)
    except Exception as exc:
        raise AgentError("Failed to analyze the Pull Request diff.") from exc


def _filter(findings: list) -> list:
    """Apply the conservative quality filter to raw findings."""
    try:
        return filter_findings(findings)
    except Exception as exc:
        raise AgentError("Failed to filter review findings.") from exc


def _format(findings: list) -> str:
    """Format findings into the final Markdown report."""
    try:
        return format_findings(findings)
    except Exception as exc:
        raise AgentError("Failed to format review findings.") from exc


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: python -m src.agent <owner> <repo> <pull_number>")
        sys.exit(1)

    owner_arg, repo_arg, pull_number_arg = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        result = run_review(owner_arg, repo_arg, int(pull_number_arg))
        print(result)
    except AgentError as e:
        print(f"AI Code Review failed: {e}")
        sys.exit(1)
