# ai-code-review-agent

AI-powered agent that automatically reviews GitHub Pull Requests, detects bugs, security issues, and meaningful code-quality problems using an LLM, and posts review comments directly on the PR.

## AI Code Review Agent

* GitHub Pull Request integration
* Ollama + Qwen2.5-Coder
* Structured `ReviewFinding` output
* Conservative finding filter
* Changed-line scope validation
* Automated GitHub Actions review
* Automatic Pull Request comments

## Architecture

```text
Pull Request
↓
GitHub Actions
↓
Python Agent
↓
GitHub Diff
↓
Ollama + Qwen2.5-Coder
↓
Changed-Line Scope Validation
↓
Finding Filter
↓
Markdown Formatter
↓
GitHub PR Comment
```

Each Pull Request triggers a GitHub Actions workflow. The Python agent retrieves the PR's changed files and patches from the GitHub API, sends the changed patch content to Ollama for analysis, validates every finding against the actual changed lines, filters out low-value findings, formats the result as Markdown, and posts it as a comment on the Pull Request.

## Overview

This project is an MVP AI code review assistant for Python repositories. It is designed as a pre-review support tool: it surfaces potential bugs, security issues, and meaningful code-quality problems for a human reviewer to confirm, not as a replacement for human review.

## Running Locally vs. GitHub Actions CI

* **Local development:** Ollama with the `qwen2.5-coder:7b` model can be run on the developer's own machine to test and iterate on the agent before pushing changes.
* **GitHub Actions CI:** Ollama is installed and started on the GitHub-hosted runner for each workflow run. The CI pipeline does not connect to the developer's local machine.

## Key Capabilities

* **GitHub Pull Request diff retrieval** — fetches changed files and unified diff patches directly from the GitHub REST API.
* **Structured ReviewFinding output** — each issue is represented as a typed finding containing the file, line, type, severity, description, and suggestion.
* **Conservative STYLE filtering** — cosmetic and subjective style findings are filtered out by default.
* **Changed-file / changed-line validation** — a deterministic gate rejects findings that do not point to an actual changed file and changed line.
* **Automated GitHub Actions execution** — the review pipeline runs automatically when a PR is opened or updated.
* **Automatic Pull Request comments** — the final Markdown review is posted directly to the PR using the GitHub CLI and the built-in `GITHUB_TOKEN`.

## LLM Provider

This MVP uses **Ollama** with **qwen2.5-coder:7b** — locally during development and on the GitHub-hosted runner during CI. No external paid LLM API is required for this MVP.

## Status

This is a working MVP demonstrated on Pull Requests in this repository. It is not tuned or benchmarked for production scale or large repositories..
