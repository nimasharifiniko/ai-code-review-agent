"""
Temporary manual integration test script for GitHub API access.

This script verifies that the GitHub client can successfully:
- Load the GitHub token from environment variables
- Authenticate with the GitHub API
- Retrieve diff information from the real test Pull Request (#1)

Usage:
    python src/test_github_connection.py
"""

import sys
from src.config import get_github_token, ConfigError
from src.github_client import GitHubClient, GitHubAPIError


def main() -> None:
    """Run the GitHub integration test against the real test PR."""
    print("=" * 60)
    print("GitHub API Integration Test")
    print("=" * 60)

    # Define the test Pull Request details
    OWNER = "nimasharifiniko"
    REPO = "ai-code-review-agent"
    PR_NUMBER = 1

    print(f"Repository: {OWNER}/{REPO}")
    print(f"Pull Request: #{PR_NUMBER}")
    print("=" * 60)

    # Step 1: Load the GitHub token
    print("\n[1] Loading GitHub token...")
    try:
        token = get_github_token()
        print("✅ Token loaded successfully.")
    except ConfigError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    # Step 2: Create the GitHub client
    print("\n[2] Creating GitHub client...")
    try:
        client = GitHubClient(token=token)
        print("✅ GitHub client created.")
    except GitHubAPIError as e:
        print(f"❌ GitHub client creation failed: {e}")
        sys.exit(1)

    # Step 3: Retrieve diff from the test Pull Request
    print(f"\n[3] Retrieving diff from Pull Request #{PR_NUMBER}...")

    try:
        diff_entries = client.get_pull_request_diff(
            owner=OWNER,
            repo=REPO,
            pull_number=PR_NUMBER,
        )
        print("✅ API request succeeded.")
    except GitHubAPIError as e:
        print(f"❌ Failed to retrieve PR diff: {e}")
        sys.exit(1)

    # Step 4: Display the results
    print(f"\n[4] Results: Found {len(diff_entries)} changed file(s)")

    if not diff_entries:
        print("    No files changed in this Pull Request.")
        return

    print("\n" + "-" * 60)

    for idx, entry in enumerate(diff_entries, 1):
        print(f"\nFile #{idx}: {entry.filename}")
        print(f"  Status: {entry.status}")

        if entry.patch:
            patch_lines = entry.patch.split("\n")
            if len(patch_lines) > 10:
                preview = "\n".join(patch_lines[:10])
                print(f"  Patch: {len(patch_lines)} lines (showing first 10)")
                print("  ```diff")
                for line in preview.split("\n"):
                    print(f"  {line}")
                if len(patch_lines) > 10:
                    print(f"  ... ({len(patch_lines) - 10} more lines)")
                print("  ```")
            else:
                print(f"  Patch: {len(patch_lines)} lines")
                print("  ```diff")
                for line in entry.patch.split("\n"):
                    print(f"  {line}")
                print("  ```")
        else:
            print("  Patch: Not available")

        print("-" * 40)

    print("\n✅ Integration test completed successfully.")
    print(
        f"   Retrieved diff for {len(diff_entries)} file(s) from PR #{PR_NUMBER}.")


if __name__ == "__main__":
    main()
