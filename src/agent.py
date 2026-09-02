"""
Application-level orchestration layer for the AI Code Review Agent.

This module coordinates the existing review pipeline components — it
does not implement GitHub communication, LLM analysis, filtering, or
formatting itself. Those responsibilities remain in their respective
modules; this file only wires them together into a single call:

    Pull Request (owner, repo, pull_number)
        -> list[ChangedFile] (github_client.py)
        -> changed-lines diff text (built here, from GitHub patches only)
        -> findings (code_analyzer.py)
        -> findings scoped to actually changed files/lines (this module)
        -> filtered findings (finding_filter.py)
        -> Markdown (formatter.py)
"""

import logging
import re

from src.config import get_github_token
from src.github_client import GitHubClient, ChangedFile
from src.code_analyzer import analyze_diff
from src.finding_filter import filter_findings
from src.formatter import format_findings
from src.review_schema import ReviewFinding

logger = logging.getLogger(__name__)

# Matches a unified diff hunk header, e.g.:
#   @@ -1,5 +1,10 @@
#   @@ -5 +5 @@
# Group 3 is the new-file starting line number (old-file range is
# not needed for changed-line scoping).
_HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


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
                    changed-line scoping, filtering, or formatting).
    """
    changed_files = _get_changed_files(owner, repo, pull_number)

    if not changed_files:
        logger.info(
            "No changed files for %s/%s#%d — skipping analysis.", owner, repo, pull_number)
        return format_findings([])

    diff_text = _build_changed_lines_diff(changed_files)

    if not diff_text.strip():
        # No file in this PR had a usable GitHub patch (e.g. binary
        # files, or files GitHub omits patches for). We do not send
        # anything to the LLM in that case — there is nothing
        # reviewable, and we must not ask it to guess.
        logger.info(
            "No reviewable patch content for %s/%s#%d — skipping analysis.",
            owner, repo, pull_number,
        )
        return format_findings([])

    changed_line_map = _get_changed_line_map(changed_files)

    raw_findings = _analyze(diff_text)

    scoped_findings = _filter_findings_to_changed_lines(
        raw_findings, changed_line_map)

    filtered_findings = _filter(scoped_findings)

    markdown = _format(filtered_findings)

    logger.info(
        "Review complete for %s/%s#%d: %d changed file(s), "
        "%d raw finding(s), %d scoped finding(s), %d final finding(s).",
        owner, repo, pull_number,
        len(changed_files), len(raw_findings), len(
            scoped_findings), len(filtered_findings),
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


def _build_changed_lines_diff(changed_files: list[ChangedFile]) -> str:
    """
    Build a strict, changed-lines-only review input from GitHub's
    unified diff patches.

    This function uses ONLY the patch text already supplied by
    GitHub's Pull Request Files API (ChangedFile.patch). It never
    reads files from the local checkout and never expands the diff
    with surrounding repository code — the LLM must not see anything
    beyond what GitHub reports as changed.

    Files without a patch (e.g. binary files, or files GitHub omits
    a patch for) are skipped entirely rather than being sent to the
    LLM as a bare filename, since a filename alone is not reviewable
    code and would invite speculation.

    Args:
        changed_files: Changed files as returned by GitHubClient.

    Returns:
        str: A diff-like text containing only files that had a real
             GitHub patch, each prefixed with its header and status.
             Empty string if no file had a usable patch.

    Raises:
        AgentError: If patch processing fails unexpectedly.
    """
    try:
        sections = [
            _format_changed_file_patch(changed_file)
            for changed_file in changed_files
            if changed_file.patch
        ]
        return "\n\n".join(sections)
    except Exception as exc:
        raise AgentError(
            "Failed to prepare diff text from changed files.") from exc


def _format_changed_file_patch(changed_file: ChangedFile) -> str:
    """
    Format a single ChangedFile's GitHub patch as a review-input section.

    The patch itself (hunk headers, added/removed/context lines) is
    used exactly as GitHub supplied it — it is not rewritten,
    trimmed, or expanded. Hunk headers (e.g. "@@ -1,5 +1,10 @@") are
    preserved so the model can determine new-file line numbers.
    """
    header = (
        f"diff --git a/{changed_file.filename} b/{changed_file.filename}\n"
        f"status: {changed_file.status}"
    )

    return f"{header}\n{changed_file.patch}"


def _get_changed_line_map(changed_files: list[ChangedFile]) -> dict[str, set[int]]:
    """
    Build an exact map of filename -> set of valid new-file changed
    line numbers, derived only from GitHub's unified diff patches.

    This is the deterministic source of truth used to reject any LLM
    finding that does not point to a real added/changed line in a
    real changed file. Files without a patch (binary files, deleted
    files with no usable new-file lines, etc.) simply contribute no
    entries — they are not treated as an error.

    Args:
        changed_files: Changed files as returned by GitHubClient.

    Returns:
        dict[str, set[int]]: e.g. {"src/demo_bug.py": {2, 5}}

    Raises:
        AgentError: If a patch cannot be parsed as a unified diff.
    """
    changed_line_map: dict[str, set[int]] = {}

    for changed_file in changed_files:
        if not changed_file.patch:
            # No patch means no usable new-file line numbers for this
            # file (binary file, or a file GitHub omitted a patch
            # for). This is not an error condition.
            continue

        try:
            line_numbers = _parse_added_lines(changed_file.patch)
        except Exception as exc:
            raise AgentError(
                f"Failed to parse diff hunks for changed file: {changed_file.filename}."
            ) from exc

        if line_numbers:
            changed_line_map[changed_file.filename] = line_numbers

    return changed_line_map


def _parse_added_lines(patch: str) -> set[int]:
    """
    Parse a single file's unified diff patch and return the set of
    new-file line numbers that correspond to added/changed ("+") lines.

    Removed lines ("-"), unchanged context lines (" "), and hunk
    header lines themselves are never included.
    """
    added_lines: set[int] = set()
    new_line: int | None = None

    for line in patch.splitlines():
        hunk_match = _HUNK_HEADER_RE.match(line)
        if hunk_match:
            new_line = int(hunk_match.group(1))
            continue

        if new_line is None:
            # Line encountered before any hunk header — not part of
            # a hunk body, ignore it (e.g. diff metadata lines).
            continue

        if line.startswith("+++") or line.startswith("---"):
            # File header lines within the patch, not content lines.
            continue

        if line.startswith("+"):
            added_lines.add(new_line)
            new_line += 1
        elif line.startswith("-"):
            # Removed old-file line: does not exist in the new file,
            # so it must never be a valid finding target.
            pass
        elif line.startswith(" "):
            # Unchanged context line: exists in the new file, but is
            # not itself a changed line.
            new_line += 1
        else:
            # Blank or otherwise unrecognised line within a hunk body
            # (e.g. a fully empty context line some diffs render
            # without a leading space). Treat conservatively as
            # context: advance the line counter but do not record it.
            new_line += 1

    return added_lines


def _filter_findings_to_changed_lines(
    findings: list[ReviewFinding],
    changed_line_map: dict[str, set[int]],
) -> list[ReviewFinding]:
    """
    Keep only findings that point to a real changed file and a real
    added/changed line within that file, per changed_line_map.

    This is a deterministic scope gate, not a correctness judgment:
    it never evaluates whether a finding is right, only whether it
    points somewhere that could plausibly be right. Order is
    preserved and the input list is never mutated.

    Args:
        findings:          Raw findings from analyze_diff().
        changed_line_map:  Output of _get_changed_line_map().

    Returns:
        list[ReviewFinding]: A new, scoped list.
    """
    return [
        finding
        for finding in findings
        if finding.file in changed_line_map
        and finding.line in changed_line_map[finding.file]
    ]


def _analyze(diff: str) -> list[ReviewFinding]:
    """Run LLM analysis on the diff text."""
    try:
        return analyze_diff(diff)
    except Exception as exc:
        # Log the underlying exception (type, message, and traceback)
        # before wrapping it in a safe AgentError. This is diagnostic
        # only — it never logs the diff itself, tokens, API keys, or
        # environment variables.
        logger.exception(
            "LLM analysis failed: %s: %s",
            type(exc).__name__,
            exc,
        )
        raise AgentError("Failed to analyze the Pull Request diff.") from exc


def _filter(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    """Apply the conservative quality filter to scoped findings."""
    try:
        return filter_findings(findings)
    except Exception as exc:
        raise AgentError("Failed to filter review findings.") from exc


def _format(findings: list[ReviewFinding]) -> str:
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
