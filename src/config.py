"""
Configuration module for loading environment variables.

This module provides a clean interface for accessing application configuration
from environment variables, with proper error handling and security practices.
"""

import os
from typing import Optional

from dotenv import load_dotenv


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


def get_github_token() -> str:
    """
    Retrieve the GitHub token from environment variables.

    Loads the .env file and returns the GITHUB_TOKEN value.
    Raises a clear error if the token is missing or empty.

    Returns:
        The GitHub token as a string.

    Raises:
        ConfigError: If GITHUB_TOKEN is not set or is empty.
    """
    # Load environment variables from .env file
    load_dotenv()

    token: Optional[str] = os.getenv("GITHUB_TOKEN")

    if not token or not token.strip():
        raise ConfigError(
            "GITHUB_TOKEN is not set. Please add it to your .env file."
        )

    # Return the token without logging or printing it
    return token.strip()
