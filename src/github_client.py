"""
GitHub API client for retrieving Pull Request information.

This module provides a clean abstraction for interacting with the GitHub REST API
to fetch changed files and diff information from a Pull Request with full pagination support.
"""

import requests
from dataclasses import dataclass
from typing import List, Optional


class GitHubAPIError(Exception):
    """Base exception for GitHub API client errors."""
    pass


@dataclass
class ChangedFile:
    """
    Represents a file changed in a Pull Request.

    Attributes:
        filename: Path to the file in the repository.
        status: Status of the change (modified, added, removed, renamed, etc.).
        additions: Number of lines added.
        deletions: Number of lines deleted.
        changes: Total number of changes (additions + deletions).
        patch: The git patch diff for the file (may be None if patch is not available).
    """
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None


@dataclass
class DiffEntry:
    """
    Simplified representation of a diff for a single file.

    Attributes:
        filename: Path to the file in the repository.
        status: Status of the change (modified, added, removed, renamed, etc.).
        patch: The git patch diff for the file (may be None if not available).
    """
    filename: str
    status: str
    patch: Optional[str] = None


class GitHubClient:
    """
    Client for interacting with the GitHub REST API.

    Provides methods to retrieve Pull Request data with proper error handling
    and pagination support.

    Example:
        client = GitHubClient(token="ghp_xxx")
        files = client.get_pull_request_files("owner", "repo", 123)
        diff_entries = client.get_pull_request_diff("owner", "repo", 123)
    """

    BASE_URL = "https://api.github.com"
    MAX_PER_PAGE = 100

    def __init__(self, token: str, timeout: int = 30):
        """
        Initialize the GitHub client.

        Args:
            token: GitHub Personal Access Token with appropriate permissions.
            timeout: Request timeout in seconds.

        Raises:
            GitHubAPIError: If the token is empty or invalid.
        """
        if not token or not token.strip():
            raise GitHubAPIError("GitHub token cannot be empty.")
        self._token = token.strip()
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _paginated_get(self, url: str, per_page: int = 100) -> List[dict]:
        """
        Perform a paginated GET request to the GitHub API.

        This method handles pagination by following the 'next' link in the
        Link header, falling back to page-based iteration when the Link header
        is not provided.

        Args:
            url: Full URL for the request.
            per_page: Number of items per page (max 100).

        Returns:
            Combined list of all items from all pages.

        Raises:
            GitHubAPIError: If the request fails or returns an error status.
        """
        if per_page < 1:
            raise GitHubAPIError("per_page must be at least 1.")
        if per_page > self.MAX_PER_PAGE:
            raise GitHubAPIError(f"per_page cannot exceed {self.MAX_PER_PAGE}.")

        params = {"per_page": per_page}
        results = []

        while True:
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
            except requests.exceptions.RequestException as e:
                raise GitHubAPIError(f"Request failed: {e}") from e

            # Handle HTTP error statuses
            if response.status_code == 401:
                raise GitHubAPIError("Authentication failed. Check your GitHub token.")
            elif response.status_code == 403:
                raise GitHubAPIError("Access forbidden. Insufficient permissions or rate limit exceeded.")
            elif response.status_code == 404:
                raise GitHubAPIError("Resource not found. Verify the repository and pull request.")
            elif response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", "Unknown error")
                except ValueError:
                    error_msg = response.text or "Unknown error"
                raise GitHubAPIError(f"GitHub API error ({response.status_code}): {error_msg}")

            # Parse JSON response
            try:
                data = response.json()
            except ValueError:
                raise GitHubAPIError("Invalid JSON response from GitHub API.")

            if not isinstance(data, list):
                raise GitHubAPIError(f"Unexpected response type: expected list, got {type(data).__name__}")

            results.extend(data)

            # If the number of items is less than requested per_page, this is the last page
            if len(data) < per_page:
                break

            # Try to follow the 'next' link from the Link header
            next_url = self._extract_next_link(response.headers.get("Link", ""))
            if next_url:
                url = next_url
                params = None
            else:
                # Fallback: manual page increment (if no Link header)
                if "page" not in params:
                    params["page"] = 1
                params["page"] += 1

        return results

    @staticmethod
    def _extract_next_link(link_header: str) -> Optional[str]:
        """
        Extract the URL from the 'next' link in the Link header.

        GitHub's Link header format:
        <https://api.github.com/...>; rel="next", <https://api.github.com/...>; rel="last"

        Args:
            link_header: The value of the Link header.

        Returns:
            The URL for the next page, or None if not found.
        """
        if not link_header:
            return None
        for link in link_header.split(","):
            parts = link.split(";")
            if len(parts) == 2 and parts[1].strip() == 'rel="next"':
                url = parts[0].strip()
                if url.startswith("<") and url.endswith(">"):
                    return url[1:-1]
        return None

    def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        per_page: int = 100,
    ) -> List[ChangedFile]:
        """
        Retrieve all files changed in a Pull Request with full pagination support.

        Args:
            owner: Repository owner (user or organization).
            repo: Repository name.
            pull_number: Pull Request number.
            per_page: Number of items per page (default 100, max 100).

        Returns:
            List of ChangedFile objects representing each changed file.

        Raises:
            GitHubAPIError: If the API call fails.
        """
        if not owner or not repo:
            raise GitHubAPIError("Owner and repository name are required.")
        if pull_number <= 0:
            raise GitHubAPIError("Pull number must be a positive integer.")

        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/files"
        raw_files = self._paginated_get(url, per_page=per_page)

        changed_files = []
        for raw in raw_files:
            changed_files.append(
                ChangedFile(
                    filename=raw.get("filename", ""),
                    status=raw.get("status", ""),
                    additions=raw.get("additions", 0),
                    deletions=raw.get("deletions", 0),
                    changes=raw.get("changes", 0),
                    patch=raw.get("patch"),  # can be None
                )
            )
        return changed_files

    def get_pull_request_diff(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        per_page: int = 100,
    ) -> List[DiffEntry]:
        """
        Retrieve diff information for all files changed in a Pull Request.

        This method provides a focused abstraction for obtaining the diff content,
        reusing the same underlying API call as get_pull_request_files() but
        returning a simplified structure containing only filename, status, and patch.

        Args:
            owner: Repository owner (user or organization).
            repo: Repository name.
            pull_number: Pull Request number.
            per_page: Number of items per page (default 100, max 100).

        Returns:
            List of DiffEntry objects, each containing filename, status, and patch.

        Raises:
            GitHubAPIError: If the API call fails.
        """
        # Reuse the files endpoint to avoid duplicate requests
        changed_files = self.get_pull_request_files(owner, repo, pull_number, per_page)

        # Map to simplified DiffEntry objects
        diff_entries = []
        for file in changed_files:
            diff_entries.append(
                DiffEntry(
                    filename=file.filename,
                    status=file.status,
                    patch=file.patch,
                )
            )
        return diff_entries