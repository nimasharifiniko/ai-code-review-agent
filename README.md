حتماً. این هم **کل README به‌صورت یک کد واحد** که می‌تونی کامل Copy کنی و مستقیم جایگزین محتوای فایل `README.md` کنی:

````markdown
# AI Code Review Agent

An AI-powered code review agent that automatically reviews GitHub Pull Requests, analyzes changed code, validates findings, and posts actionable review comments directly to the Pull Request.

The project combines Python, GitHub Actions, Ollama, and Qwen2.5-Coder to create an automated code review workflow.

## 🚀 How It Works

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
````

When a Pull Request is created or updated, GitHub Actions automatically starts the review workflow.

The agent retrieves the actual changed files and diff, sends the relevant code to the LLM for analysis, validates the generated findings, filters low-value results, and posts the final review back to GitHub.

## 🧠 Key Features

* Automated GitHub Pull Request code review
* GitHub API integration
* GitHub Actions automation
* Local LLM inference with Ollama
* Qwen2.5-Coder for code analysis
* Structured review findings
* Conservative finding filtering
* Deterministic changed-line scope validation
* Automatic Markdown formatting
* Automatic comments on Pull Requests

## 🔍 Structured Review Findings

Each finding is represented as a structured object containing:

* **File**
* **Line**
* **Type**
* **Severity**
* **Description**
* **Suggestion**

This keeps the review output structured and predictable instead of relying only on free-form AI-generated text.

## 🛡️ Changed-Line Validation

One of the important design decisions in this project is deterministic validation of AI findings.

The agent checks that reported findings belong to:

* files that were actually changed
* lines that were actually changed in the Pull Request

This helps prevent the model from reporting unrelated code outside the scope of the Pull Request.

## 🔧 Tech Stack

* Python
* GitHub API
* GitHub Actions
* Ollama
* Qwen2.5-Coder
* REST APIs
* Git / GitHub

## 📁 Project Structure

```text
ai-code-review-agent/
│
├── src/
│   ├── agent.py
│   ├── github_client.py
│   ├── code_analyzer.py
│   ├── finding_filter.py
│   ├── formatter.py
│   └── review_schema.py
│
├── test_code_review.py
├── test_github_connection.py
│
├── .github/
│   └── workflows/
│       └── code-review.yml
│
├── .env
├── .gitignore
└── README.md
```

## ⚙️ Local Development

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Ollama

Install Ollama and make sure it is running locally.

Then pull the coding model:

```bash
ollama pull qwen2.5-coder:7b
```

### 3. Configure environment variables

Create a `.env` file:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
GITHUB_TOKEN=your_github_token
```

> Never commit your `.env` file or expose your GitHub token.

### 4. Run a review locally

```bash
python -m src.agent <owner> <repo> <pull_request_number>
```

Example:

```bash
python -m src.agent nimasharifiniko ai-code-review-agent 3
```

## 🤖 GitHub Actions

The project includes a GitHub Actions workflow that automatically runs the code review agent when a Pull Request is created or updated.

The workflow:

1. Checks out the repository
2. Sets up Python
3. Loads the required configuration
4. Retrieves the Pull Request changes
5. Runs the AI code review
6. Validates the findings
7. Formats the review
8. Posts the result back to the Pull Request

## 💬 Example Review

```text
## 🤖 AI Code Review

### 🟠 High — Bug

**`src/demo_bug.py:2`**

Division by zero detected in the divide function.

**Suggestion:** Add a check to prevent division by zero, or handle the exception.
```

## 🎯 Project Goal

The goal of this project is not simply to generate AI text.

It is to build a practical AI engineering system that combines:

* LLM reasoning
* deterministic validation
* API integration
* automation
* structured outputs
* CI/CD workflows

The result is an automated code review pipeline that connects a GitHub Pull Request to an AI-powered review and returns the result directly to the developer.

## 📌 Project Status

The core workflow is implemented and tested with real GitHub Pull Requests.

The system can automatically analyze Pull Request changes and post structured review comments back to GitHub.

---

Built with Python, GitHub Actions, Ollama, and Qwen2.5-Coder.

```
```
