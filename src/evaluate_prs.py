"""
Repeatable evaluation utility for the AI Code Review Agent.

Runs the real end-to-end pipeline (via src.agent.run_review) against
a small, configurable list of Pull Requests and prints the resulting
Markdown review for each one.

This script does NOT change agent behavior, prompts, filtering, or
scoring. It only collects evidence — a human reviewer classifies each
reported finding as TRUE_POSITIVE, FALSE_POSITIVE, or MISSED_ISSUE
after reading the output.

Run directly with:

    python -m src.evaluate_prs
"""

from src.agent import run_review, AgentError

# Configurable list of Pull Requests to evaluate.
# Only PRs known to exist in the current repository are listed here —
# no PR numbers are fabricated.
PR_CASES: list[dict] = [
    {
        "owner": "nimasharifiniko",
        "repo": "ai-code-review-agent",
        "pull_number": 1,
        "label": "PR 1",
    },
]


def evaluate_pr(case: dict) -> None:
    """
    Run the real review pipeline for a single PR case and print the
    resulting Markdown review, or a safe error message on failure.

    Args:
        case: A dict with "owner", "repo", "pull_number", and "label".
    """
    label = case["label"]
    owner = case["owner"]
    repo = case["repo"]
    pull_number = case["pull_number"]

    print("=" * 60)
    print(f"PR: {label}")
    print("=" * 60)
    print()
    print(f"Repository: {owner}/{repo}")
    print(f"Pull Request: #{pull_number}")
    print()

    try:
        markdown = run_review(owner=owner, repo=repo, pull_number=pull_number)
    except AgentError as exc:
        print(f"Review failed for {label}: {exc}")
        print()
        return
    except Exception as exc:
        print(f"Unexpected error for {label}: {type(exc).__name__}: {exc}")
        print()
        return

    print("Review output:")
    print()
    print(markdown)
    print()


def _print_manual_evaluation_header() -> None:
    """Print a header prompting the human reviewer to manually classify findings."""
    print("=" * 60)
    print("MANUAL EVALUATION")
    print("=" * 60)
    print()
    print("For each finding printed above, classify it as one of:")
    print("  - TRUE_POSITIVE")
    print("  - FALSE_POSITIVE")
    print("  - MISSED_ISSUE")
    print()
    print("Also consider:")
    print("  - changed-line accuracy")
    print("  - severity quality")
    print("  - actionability")
    print()


def main() -> None:
    for case in PR_CASES:
        evaluate_pr(case)

    _print_manual_evaluation_header()


if __name__ == "__main__":
    main()
