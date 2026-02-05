#!/usr/bin/env python3
"""
AI Code Review for Azure DevOps Pull Requests
Uses GitHub Copilot CLI instead of OpenAI API for code analysis.

Architecture:
  - Fetches PR diff from Azure DevOps REST API
  - Sends diff to GitHub Copilot CLI for review
  - Posts review comments back to the PR via Azure DevOps API

Prerequisites:
  - GitHub Copilot CLI installed (auto-installed by install_copilot_cli())
  - GitHub PAT with Copilot access (set as GH_TOKEN env var)
  - Azure DevOps access token (System.AccessToken or PAT)
"""

import os
import sys
import json
import subprocess
import tempfile
import base64
import logging
import platform
import shutil
from urllib import request, error, parse
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if os.environ.get("INPUT_DEBUG", "false").lower() == "true" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("copilot-code-review")

# Azure DevOps environment variables (set by the pipeline agent)
SYSTEM_COLLECTIONURI = os.environ.get("SYSTEM_COLLECTIONURI", "")
SYSTEM_TEAMPROJECT = os.environ.get("SYSTEM_TEAMPROJECT", "")
BUILD_REPOSITORY_NAME = os.environ.get("BUILD_REPOSITORY_NAME", "")
SYSTEM_PULLREQUEST_PULLREQUESTID = os.environ.get("SYSTEM_PULLREQUEST_PULLREQUESTID", "")

# Task inputs (set by task.json -> index.ts -> env vars)
GITHUB_PAT = os.environ.get("INPUT_GITHUB_PAT", "")
ADO_TOKEN = os.environ.get("SYSTEM_ACCESSTOKEN", "") or os.environ.get("INPUT_ADO_PAT", "")
COPILOT_MODEL = os.environ.get("INPUT_COPILOT_MODEL", "")
MAX_FILES = int(os.environ.get("INPUT_MAX_FILES", "50"))
MAX_LINES_PER_FILE = int(os.environ.get("INPUT_MAX_LINES_PER_FILE", "1000"))
DEBUG = os.environ.get("INPUT_DEBUG", "false").lower() == "true"
CONTINUE_ON_ERROR = os.environ.get("INPUT_CONTINUE_ON_ERROR", "true").lower() == "true"
CUSTOM_PROMPT = os.environ.get("INPUT_CUSTOM_PROMPT", "")
PROMPT_FILE = os.environ.get("INPUT_PROMPT_FILE", "")

# Azure DevOps API version
ADO_API_VERSION = "7.1"

# ---------------------------------------------------------------------------
# Skill-Based Review System
# ---------------------------------------------------------------------------

# Path to skill files (relative to this script)
SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "code-review-skill")

# Mapping of file extensions to language-specific skill files
LANGUAGE_SKILL_MAP = {
    # Python
    ".py": "python.md",
    ".pyw": "python.md",
    ".pyx": "python.md",
    # JavaScript/TypeScript
    ".js": "javascript.md",
    ".jsx": "javascript.md",
    ".ts": "javascript.md",
    ".tsx": "javascript.md",
    ".mjs": "javascript.md",
    ".cjs": "javascript.md",
    # C#
    ".cs": "csharp.md",
    ".csx": "csharp.md",
    # Java
    ".java": "java.md",
    ".kt": "java.md",
    ".kts": "java.md",
    # Rust
    ".rs": "rust.md",
    # Go
    ".go": "go.md",
    # C/C++
    ".c": "cpp.md",
    ".cpp": "cpp.md",
    ".cc": "cpp.md",
    ".cxx": "cpp.md",
    ".h": "cpp.md",
    ".hpp": "cpp.md",
    ".hxx": "cpp.md",
}

# Framework detection patterns
FRAMEWORK_PATTERNS = {
    "frontend.md": [
        "react", "vue", "angular", "@angular", "svelte", "vite",
        "next", "nuxt", "remix", ".jsx", ".tsx", ".vue", ".svelte"
    ],
    "backend.md": [
        "fastapi", "flask", "django", "express", "nest", "koa",
        "spring", "quarkus", "asp.net", "webapi", "controller"
    ],
}

# Cross-cutting concerns always loaded
CROSS_CUTTING_SKILLS = ["security.md", "architecture.md", "performance.md"]


def load_skill_file(filename: str) -> str:
    """Load a skill file from the code-review-skill directory."""
    # Check references subdirectory first
    ref_path = os.path.join(SKILL_DIR, "references", filename)
    if os.path.isfile(ref_path):
        with open(ref_path, "r", encoding="utf-8") as f:
            return f.read()

    # Check root skill directory
    root_path = os.path.join(SKILL_DIR, filename)
    if os.path.isfile(root_path):
        with open(root_path, "r", encoding="utf-8") as f:
            return f.read()

    log.warning(f"Skill file not found: {filename}")
    return ""


def detect_languages_from_diff(diff: str) -> set:
    """Detect programming languages from file extensions in the diff."""
    languages = set()

    # Parse diff headers to find file paths
    for line in diff.split("\n"):
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            path = line[6:]  # Remove "+++ b/" or "--- a/"
            if path and path != "/dev/null":
                _, ext = os.path.splitext(path)
                ext = ext.lower()
                if ext in LANGUAGE_SKILL_MAP:
                    languages.add(LANGUAGE_SKILL_MAP[ext])

    return languages


def detect_frameworks_from_diff(diff: str) -> set:
    """Detect frameworks from content patterns in the diff."""
    frameworks = set()
    diff_lower = diff.lower()

    for skill_file, patterns in FRAMEWORK_PATTERNS.items():
        for pattern in patterns:
            if pattern in diff_lower:
                frameworks.add(skill_file)
                break

    return frameworks


def build_skill_based_prompt(diff: str) -> str:
    """
    Build a comprehensive review prompt using skill files.
    Dynamically loads relevant skills based on detected languages and frameworks.
    """
    prompt_parts = []

    # 1. Load the main skill file (SKILL.md)
    main_skill = load_skill_file("SKILL.md")
    if main_skill:
        prompt_parts.append(main_skill)

    # 2. Detect and load language-specific skills
    detected_languages = detect_languages_from_diff(diff)
    log.info(f"Detected language skills: {detected_languages or 'none'}")

    for lang_skill in detected_languages:
        content = load_skill_file(lang_skill)
        if content:
            prompt_parts.append(f"\n\n---\n\n## Language Reference: {lang_skill}\n\n{content}")

    # 3. Detect and load framework-specific skills
    detected_frameworks = detect_frameworks_from_diff(diff)
    log.info(f"Detected framework skills: {detected_frameworks or 'none'}")

    for fw_skill in detected_frameworks:
        content = load_skill_file(fw_skill)
        if content:
            prompt_parts.append(f"\n\n---\n\n## Framework Reference: {fw_skill}\n\n{content}")

    # 4. Always load cross-cutting concerns (security, architecture, performance)
    for cc_skill in CROSS_CUTTING_SKILLS:
        content = load_skill_file(cc_skill)
        if content:
            # Truncate to keep within context limits (each ~10KB)
            if len(content) > 12000:
                content = content[:12000] + "\n\n[... truncated for context limits ...]"
            prompt_parts.append(f"\n\n---\n\n## {cc_skill.replace('.md', '').title()} Reference\n\n{content}")

    # 5. Add JSON output format instructions
    prompt_parts.append("""

---

## Required Output Format

After reviewing the code, respond in this EXACT JSON format:

```json
{
  "summary": "Brief overall assessment of the PR",
  "verdict": "APPROVE|REQUEST_CHANGES|COMMENT",
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "security|performance|logic|best-practice|quality|error-handling",
      "file": "path/to/file.ext",
      "line": 42,
      "title": "Short issue title",
      "description": "Detailed explanation of the problem",
      "suggestion": "Recommended fix or improvement with code example"
    }
  ]
}
```

If no issues are found, return:
```json
{
  "summary": "PR looks good. No significant issues found.",
  "verdict": "APPROVE",
  "issues": []
}
```

IMPORTANT:
- Only report real, actionable issues from the CHANGED lines (+ lines in diff)
- Do NOT flag issues in unchanged context lines
- Be specific about file paths and line numbers
- Provide concrete fix suggestions with code examples
- Respond ONLY with valid JSON, no additional text before or after
""")

    return "\n".join(prompt_parts)


# Fallback prompt if skill files are not available
DEFAULT_REVIEW_PROMPT = """You are an expert code reviewer. Analyze the following code changes from a Pull Request and provide a thorough review.

Focus on these areas:
1. **Security** - OWASP Top 10, injection vulnerabilities, authentication issues, secrets exposure
2. **Performance** - Algorithm complexity, database queries, memory management, async patterns
3. **Logic Errors** - Off-by-one errors, null/undefined handling, race conditions
4. **Best Practices** - Language idioms, framework conventions, design patterns
5. **Code Quality** - Readability, naming, DRY principle, maintainability
6. **Error Handling** - Exception handling, graceful degradation, logging

For each issue found, respond in this EXACT JSON format:
```json
{
  "summary": "Brief overall assessment of the PR",
  "verdict": "APPROVE|REQUEST_CHANGES|COMMENT",
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "security|performance|logic|best-practice|quality|error-handling",
      "file": "path/to/file.ext",
      "line": 42,
      "title": "Short issue title",
      "description": "Detailed explanation of the problem",
      "suggestion": "Recommended fix or improvement"
    }
  ]
}
```

If no issues are found, return:
```json
{
  "summary": "PR looks good. No significant issues found.",
  "verdict": "APPROVE",
  "issues": []
}
```

IMPORTANT:
- Only report real, actionable issues - not style nitpicks
- Be specific about file paths and line numbers when possible
- Provide concrete fix suggestions, not vague advice
- Respond ONLY with valid JSON, no additional text before or after
"""

# ---------------------------------------------------------------------------
# Copilot CLI Management
# ---------------------------------------------------------------------------

def find_copilot_cli() -> Optional[str]:
    """Check if GitHub Copilot CLI is already installed and return its path."""
    # Check the new standalone 'copilot' CLI first
    copilot_path = shutil.which("copilot")
    if copilot_path:
        log.info(f"Found Copilot CLI at: {copilot_path}")
        return copilot_path

    # Check 'gh copilot' extension (deprecated but may still work)
    gh_path = shutil.which("gh")
    if gh_path:
        result = subprocess.run(
            ["gh", "extension", "list"],
            capture_output=True, text=True, timeout=30
        )
        if "copilot" in result.stdout.lower():
            log.info("Found gh copilot extension")
            return "gh-copilot"

    return None


def install_copilot_cli() -> str:
    """Install GitHub Copilot CLI if not present. Returns the CLI command to use."""
    existing = find_copilot_cli()
    if existing:
        return existing

    log.info("GitHub Copilot CLI not found. Installing...")

    system = platform.system().lower()

    if system == "linux":
        # Official Copilot CLI install script for Linux
        log.info("Installing Copilot CLI on Linux...")
        try:
            # First ensure gh CLI is installed
            gh_path = shutil.which("gh")
            if not gh_path:
                log.info("Installing GitHub CLI first...")
                subprocess.run(
                    ["bash", "-c",
                     "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | "
                     "sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && "
                     "echo 'deb [arch=$(dpkg --print-architecture) "
                     "signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] "
                     "https://cli.github.com/packages stable main' | "
                     "sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null && "
                     "sudo apt-get update && sudo apt-get install -y gh"],
                    check=True, timeout=300
                )

            # Install copilot CLI via the official install script
            subprocess.run(
                ["bash", "-c", "curl -fsSL https://gh.io/copilot-install | bash"],
                check=True, timeout=300,
                env={**os.environ, "GH_TOKEN": GITHUB_PAT}
            )
        except subprocess.CalledProcessError:
            # Fallback: install gh copilot extension
            log.warning("Standalone Copilot CLI install failed, trying gh extension...")
            subprocess.run(
                ["gh", "extension", "install", "github/gh-copilot", "--force"],
                check=True, timeout=120,
                env={**os.environ, "GH_TOKEN": GITHUB_PAT}
            )
            return "gh-copilot"

    elif system == "windows":
        log.info("Installing Copilot CLI on Windows...")
        try:
            subprocess.run(
                ["winget", "install", "--id", "GitHub.CopilotCLI",
                 "--accept-source-agreements", "--accept-package-agreements"],
                check=True, timeout=300
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            log.warning("winget install failed, trying gh extension...")
            subprocess.run(
                ["gh", "extension", "install", "github/gh-copilot", "--force"],
                check=True, timeout=120,
                env={**os.environ, "GH_TOKEN": GITHUB_PAT}
            )
            return "gh-copilot"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    # Verify installation
    installed = find_copilot_cli()
    if not installed:
        raise RuntimeError(
            "Failed to install GitHub Copilot CLI. "
            "Ensure the agent has internet access and the GitHub PAT has Copilot permissions."
        )
    return installed


# ---------------------------------------------------------------------------
# Azure DevOps API Helpers
# ---------------------------------------------------------------------------

def ado_api_request(url: str, method: str = "GET", data: dict = None) -> dict:
    """Make an authenticated request to the Azure DevOps REST API."""
    if "?" in url:
        full_url = f"{url}&api-version={ADO_API_VERSION}"
    else:
        full_url = f"{url}?api-version={ADO_API_VERSION}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(f':{ADO_TOKEN}'.encode()).decode()}",
    }

    body = json.dumps(data).encode("utf-8") if data else None
    req = request.Request(full_url, data=body, headers=headers, method=method)

    log.debug(f"ADO API {method} {full_url}")

    try:
        with request.urlopen(req, timeout=30) as resp:
            response_body = resp.read().decode("utf-8")
            if response_body:
                return json.loads(response_body)
            return {}
    except error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.readable() else "No response body"
        log.error(f"ADO API error {e.code}: {error_body}")
        raise


def get_pr_details() -> dict:
    """Fetch Pull Request metadata."""
    base_url = SYSTEM_COLLECTIONURI.rstrip("/")
    project = parse.quote(SYSTEM_TEAMPROJECT)
    repo = parse.quote(BUILD_REPOSITORY_NAME)
    pr_id = SYSTEM_PULLREQUEST_PULLREQUESTID

    url = f"{base_url}/{project}/_apis/git/repositories/{repo}/pullrequests/{pr_id}"
    return ado_api_request(url)


def get_pr_iterations() -> list:
    """Get PR iterations (each push creates a new iteration)."""
    base_url = SYSTEM_COLLECTIONURI.rstrip("/")
    project = parse.quote(SYSTEM_TEAMPROJECT)
    repo = parse.quote(BUILD_REPOSITORY_NAME)
    pr_id = SYSTEM_PULLREQUEST_PULLREQUESTID

    url = f"{base_url}/{project}/_apis/git/repositories/{repo}/pullrequests/{pr_id}/iterations"
    result = ado_api_request(url)
    return result.get("value", [])


def get_pr_changes(iteration_id: int = None) -> list:
    """Fetch the list of changed files in the PR."""
    base_url = SYSTEM_COLLECTIONURI.rstrip("/")
    project = parse.quote(SYSTEM_TEAMPROJECT)
    repo = parse.quote(BUILD_REPOSITORY_NAME)
    pr_id = SYSTEM_PULLREQUEST_PULLREQUESTID

    if iteration_id:
        url = (f"{base_url}/{project}/_apis/git/repositories/{repo}"
               f"/pullrequests/{pr_id}/iterations/{iteration_id}/changes")
    else:
        # Get changes from the latest iteration
        iterations = get_pr_iterations()
        if iterations:
            latest = iterations[-1]["id"]
            url = (f"{base_url}/{project}/_apis/git/repositories/{repo}"
                   f"/pullrequests/{pr_id}/iterations/{latest}/changes")
        else:
            log.warning("No iterations found, fetching all changes")
            url = (f"{base_url}/{project}/_apis/git/repositories/{repo}"
                   f"/pullrequests/{pr_id}/changes")

    result = ado_api_request(url)
    return result.get("changeEntries", [])


def get_file_content(path: str, commit_id: str) -> str:
    """Fetch file content at a specific commit via Azure DevOps API."""
    base_url = SYSTEM_COLLECTIONURI.rstrip("/")
    project = parse.quote(SYSTEM_TEAMPROJECT)
    repo = parse.quote(BUILD_REPOSITORY_NAME)
    encoded_path = parse.quote(path)

    url = (f"{base_url}/{project}/_apis/git/repositories/{repo}"
           f"/items?path={encoded_path}&versionType=Commit"
           f"&version={commit_id}&includeContent=true")

    headers = {
        "Authorization": f"Basic {base64.b64encode(f':{ADO_TOKEN}'.encode()).decode()}",
    }

    req = request.Request(
        f"{url}&api-version={ADO_API_VERSION}",
        headers=headers
    )

    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as e:
        log.warning(f"Could not fetch file {path} at {commit_id}: {e.code}")
        return ""


def get_diff_via_git() -> str:
    """Get the PR diff using local git commands (requires fetchDepth: 0)."""
    try:
        # Get the target branch from environment
        target_branch = os.environ.get(
            "SYSTEM_PULLREQUEST_TARGETBRANCHNAME",
            os.environ.get("SYSTEM_PULLREQUEST_TARGETBRANCH", "main")
        )
        # Remove refs/heads/ prefix if present
        target_branch = target_branch.replace("refs/heads/", "")

        # Fetch the target branch
        subprocess.run(
            ["git", "fetch", "origin", target_branch],
            capture_output=True, text=True, timeout=60
        )

        # Get the diff
        result = subprocess.run(
            ["git", "diff", f"origin/{target_branch}...HEAD", "--no-color"],
            capture_output=True, text=True, timeout=120
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        else:
            log.warning(f"git diff returned no output. stderr: {result.stderr}")
            return ""

    except Exception as e:
        log.warning(f"Could not get diff via git: {e}")
        return ""


def post_pr_comment(content: str, comment_type: int = 1):
    """
    Post a comment thread on the PR.
    comment_type: 1 = Text, 2 = CodeChange, 3 = System
    """
    base_url = SYSTEM_COLLECTIONURI.rstrip("/")
    project = parse.quote(SYSTEM_TEAMPROJECT)
    repo = parse.quote(BUILD_REPOSITORY_NAME)
    pr_id = SYSTEM_PULLREQUEST_PULLREQUESTID

    url = (f"{base_url}/{project}/_apis/git/repositories/{repo}"
           f"/pullrequests/{pr_id}/threads")

    thread_data = {
        "comments": [
            {
                "parentCommentId": 0,
                "content": content,
                "commentType": comment_type,
            }
        ],
        "status": 1,  # Active
    }

    ado_api_request(url, method="POST", data=thread_data)
    log.info("Posted review comment to PR")


# ---------------------------------------------------------------------------
# Copilot CLI Review Engine
# ---------------------------------------------------------------------------

def build_review_prompt(diff: str) -> str:
    """
    Build a detailed review prompt for comprehensive code review.
    """
    # Use custom prompt if provided (highest priority)
    if CUSTOM_PROMPT:
        log.info("Using custom prompt from task input")
        prompt = CUSTOM_PROMPT
    elif PROMPT_FILE and os.path.isfile(PROMPT_FILE):
        log.info(f"Using prompt from file: {PROMPT_FILE}")
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            prompt = f.read()
    else:
        # Use detailed review prompt
        log.info("Using detailed review prompt")
        prompt = DETAILED_REVIEW_PROMPT

    return f"{prompt}\n\n## Code Changes to Review:\n\n```diff\n{diff}\n```"


# Detailed code review prompt matching OpenAI format
DETAILED_REVIEW_PROMPT = """You are an expert code reviewer. Review this Pull Request diff thoroughly.

## Review Format

Respond in this EXACT JSON format:

```json
{
  "pr_description": "Brief description of what this PR does",
  "files_changed": [
    {"file": "path/to/file.ext", "change_type": "Added|Modified|Deleted", "lines_changed": "+50/-10"}
  ],
  "overall_assessment": "APPROVE|REQUEST_CHANGES|COMMENT",
  "summary": "2-3 sentence summary of the review",
  "critical_issues": [
    {
      "title": "Issue title",
      "file": "path/to/file.ext",
      "line": 42,
      "category": "security|performance|logic|best-practice",
      "changed_code": "The actual code snippet from the diff that has the issue",
      "problem": "Detailed explanation of what's wrong and why it's dangerous",
      "impact": "What could happen if this isn't fixed",
      "solution": "Detailed fix with code example showing the correct implementation"
    }
  ],
  "high_priority": [],
  "medium_priority": [],
  "suggestions": [],
  "positive_notes": ["List of good things about the code"]
}
```

## Review Guidelines

1. **Security** - Check for OWASP Top 10: SQL injection, XSS, hardcoded secrets, weak crypto, auth issues
2. **Logic Errors** - Null reference bugs, off-by-one errors, race conditions, incorrect conditionals
3. **Performance** - Inefficient algorithms, N+1 queries, unnecessary allocations, string concatenation in loops
4. **Best Practices** - Exception handling, logging, naming conventions, SOLID principles

## Important Instructions

- Include the ACTUAL CODE SNIPPET from the diff in "changed_code" field
- Provide WORKING CODE EXAMPLES in the "solution" field
- Be specific about line numbers
- Only flag issues in CHANGED lines (lines starting with +)
- Include positive notes about good practices you observe
- If code looks good, return empty arrays for issues and explain why in summary"""


def run_copilot_review(diff: str, cli_command: str = None) -> str:
    """
    Send the diff to GitHub Copilot for review.
    Tries Copilot CLI first, falls back to GitHub Models API.
    """
    full_prompt = build_review_prompt(diff)
    log.info(f"Review prompt built ({len(full_prompt)} chars)")

    env = {
        **os.environ,
        "GH_TOKEN": GITHUB_PAT,
        "GITHUB_TOKEN": GITHUB_PAT,
    }

    # Try to install and use Copilot CLI (better models, larger context)
    try:
        cli_path = install_copilot_cli()
        if cli_path:
            log.info(f"Using Copilot CLI: {cli_path}")
            result = run_copilot_cli(full_prompt, cli_path, env)
            if result:
                return result
            log.warning("Copilot CLI returned empty, trying API fallback...")
    except Exception as e:
        log.warning(f"Copilot CLI unavailable: {e}, using API fallback...")

    # Fall back to GitHub Models API (limited models, smaller context)
    log.info("Falling back to GitHub Models API...")
    return call_github_models_api(full_prompt, env)


def run_copilot_cli(prompt: str, cli_path: str, env: dict) -> str:
    """Run review using GitHub Copilot CLI."""
    # Write prompt to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
        tmp.write(prompt)
        prompt_file = tmp.name

    try:
        # Determine model to use
        model = COPILOT_MODEL or "claude-sonnet-4.5"
        log.info(f"Running Copilot CLI with model: {model}")

        if cli_path == "gh-copilot":
            # Using gh copilot extension
            cmd = ["gh", "copilot", "suggest", "--target", "shell"]
            # Read prompt and use stdin
            with open(prompt_file, "r") as f:
                prompt_content = f.read()
            result = subprocess.run(
                cmd,
                input=prompt_content,
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
        else:
            # Using standalone copilot CLI
            result = subprocess.run(
                [cli_path, "-m", model, "-p", f"@{prompt_file}"],
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )

        if result.returncode == 0 and result.stdout.strip():
            log.info(f"Copilot CLI response received ({len(result.stdout)} chars)")
            return result.stdout.strip()

        log.warning(f"Copilot CLI returned code {result.returncode}")
        if result.stderr:
            log.warning(f"stderr: {result.stderr[:500]}")
        return None

    finally:
        try:
            os.unlink(prompt_file)
        except OSError:
            pass


def call_github_models_api(prompt: str, env: dict) -> str:
    """
    Call the GitHub Models API for code review.
    Uses the Azure-hosted GitHub Models inference endpoint.
    """
    # Supported GitHub Models API models
    # See: https://github.com/marketplace/models
    supported_models = {
        # OpenAI
        "gpt-4o",
        "gpt-4o-mini",
        # Meta Llama 3.1
        "Meta-Llama-3.1-405B-Instruct",
        "Meta-Llama-3.1-70B-Instruct",
        "Meta-Llama-3.1-8B-Instruct",
        # Meta Llama 3
        "Meta-Llama-3-70B-Instruct",
        "Meta-Llama-3-8B-Instruct",
        # Mistral
        "Mistral-large-2407",
        "Mistral-Nemo",
        # AI21
        "AI21-Jamba-Instruct",
    }

    # Default to GPT-4o for best code review quality
    requested_model = COPILOT_MODEL or "gpt-4o"
    model = requested_model if requested_model in supported_models else "gpt-4o"

    log.info(f"Using GitHub Models API with model: {model}")

    # Standard chat completions format (OpenAI-compatible)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert code reviewer. Respond only with valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 8192
    }

    # GitHub Models API endpoint (the only working endpoint)
    api_url = "https://models.inference.ai.azure.com/chat/completions"
    gh_token = env.get('GH_TOKEN', '')

    if not gh_token:
        raise RuntimeError("GitHub token (GH_TOKEN) is not set")

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Content-Type": "application/json",
    }

    try:
        log.info(f"Calling GitHub Models API: {api_url}")
        log.info(f"Using model: {model}")

        req = request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        with request.urlopen(req, timeout=300) as resp:
            response = json.loads(resp.read().decode("utf-8"))

            # Standard OpenAI completions format
            choices = response.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                log.info(f"GitHub Models API response received ({len(content)} chars)")
                return content

            log.warning("No choices in API response")
            return json.dumps(response)

    except error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.readable() else "No response body"
        log.error(f"GitHub Models API error {e.code}: {error_body}")
        raise RuntimeError(f"GitHub Models API failed with HTTP {e.code}: {error_body}")

    except Exception as e:
        log.error(f"GitHub Models API request failed: {e}")
        raise RuntimeError(f"GitHub Models API failed: {str(e)}")


# ---------------------------------------------------------------------------
# Review Parsing & Formatting
# ---------------------------------------------------------------------------

def parse_review_response(raw_response: str) -> dict:
    """Parse the JSON review response from Copilot."""
    text = raw_response.strip()

    # Remove markdown code fences if present
    if "```json" in text:
        try:
            start = text.index("```json") + 7
            end = text.rindex("```")
            text = text[start:end].strip()
        except ValueError:
            # No closing fence, take everything after ```json
            start = text.index("```json") + 7
            text = text[start:].strip()
    elif "```" in text:
        try:
            start = text.index("```") + 3
            end = text.rindex("```")
            text = text[start:end].strip()
        except ValueError:
            start = text.index("```") + 3
            text = text[start:].strip()

    # Try to find JSON object boundaries
    if text.startswith("{"):
        # Find matching closing brace
        brace_count = 0
        json_end = 0
        for i, char in enumerate(text):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break
        if json_end > 0:
            text = text[:json_end]

    # Try to parse JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.warning(f"JSON parse error: {e}")

        # Try to fix common truncation issues
        try:
            # Add missing closing brackets
            fixed = text.rstrip()
            open_braces = fixed.count("{") - fixed.count("}")
            open_brackets = fixed.count("[") - fixed.count("]")

            # Remove incomplete last field if truncated
            if fixed.endswith('"') or fixed.endswith(','):
                last_complete = max(fixed.rfind('}'), fixed.rfind(']'))
                if last_complete > 0:
                    fixed = fixed[:last_complete + 1]

            # Add missing closures
            fixed += "]" * open_brackets + "}" * open_braces

            result = json.loads(fixed)
            log.info("Successfully parsed JSON after fixing truncation")
            return result
        except json.JSONDecodeError:
            pass

        # Final fallback: extract what we can
        log.warning("Could not parse JSON, extracting fields manually")
        return extract_review_fields(raw_response)


def extract_review_fields(raw_response: str) -> dict:
    """Extract review fields from raw response when JSON parsing fails."""
    import re

    result = {
        "summary": "",
        "overall_assessment": "COMMENT",
        "critical_issues": [],
        "high_priority": [],
        "medium_priority": [],
        "suggestions": [],
        "positive_notes": [],
        "raw_response": None
    }

    text = raw_response

    # Try to extract summary
    summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', text)
    if summary_match:
        result["summary"] = summary_match.group(1)

    # Try to extract overall_assessment
    assessment_match = re.search(r'"overall_assessment"\s*:\s*"([^"]+)"', text)
    if assessment_match:
        result["overall_assessment"] = assessment_match.group(1)

    # Try to extract pr_description
    pr_desc_match = re.search(r'"pr_description"\s*:\s*"([^"]+)"', text)
    if pr_desc_match:
        result["pr_description"] = pr_desc_match.group(1)

    # Try to extract individual issues using regex
    issue_pattern = r'\{\s*"title"\s*:\s*"([^"]+)"[^}]*"file"\s*:\s*"([^"]+)"[^}]*"line"\s*:\s*(\d+)[^}]*"category"\s*:\s*"([^"]+)"[^}]*"problem"\s*:\s*"([^"]+)"'

    for match in re.finditer(issue_pattern, text, re.DOTALL):
        issue = {
            "title": match.group(1),
            "file": match.group(2),
            "line": int(match.group(3)),
            "category": match.group(4),
            "problem": match.group(5),
        }

        # Try to extract solution for this issue
        solution_match = re.search(r'"solution"\s*:\s*"([^"]{10,})"', text[match.end():match.end()+2000])
        if solution_match:
            issue["solution"] = solution_match.group(1)

        # Try to extract changed_code
        code_match = re.search(r'"changed_code"\s*:\s*"([^"]+)"', text[match.start():match.end()+500])
        if code_match:
            issue["changed_code"] = code_match.group(1)

        # Categorize by severity based on category
        if issue["category"] == "security":
            result["critical_issues"].append(issue)
        elif issue["category"] in ["logic", "performance"]:
            result["high_priority"].append(issue)
        elif issue["category"] == "best-practice":
            result["suggestions"].append(issue)
        else:
            result["medium_priority"].append(issue)

    # If we extracted issues, don't show raw response
    if result["critical_issues"] or result["high_priority"] or result["medium_priority"] or result["suggestions"]:
        log.info(f"Extracted {len(result['critical_issues'])} critical, {len(result['high_priority'])} high priority issues")
    else:
        # Show truncated raw response as fallback
        result["raw_response"] = raw_response[:3000]

    return result


def format_review_comment(review: dict) -> str:
    """Format the review into a detailed markdown comment for Azure DevOps."""
    lines = []

    # Header
    lines.append("## 🤖 AI Code Review (Powered by GitHub Copilot)")
    lines.append("")

    # PR Description
    pr_desc = review.get("pr_description", "")
    if pr_desc:
        lines.append(f"**PR/Change Description:** {pr_desc}")
        lines.append("")

    # Files Changed Table
    files_changed = review.get("files_changed", [])
    if files_changed:
        lines.append("### Files Reviewed")
        lines.append("")
        lines.append("| File | Change Type | Lines Changed |")
        lines.append("|------|-------------|---------------|")
        for f in files_changed[:10]:  # Limit to 10 files
            file_name = f.get("file", "Unknown")
            change_type = f.get("change_type", "Modified")
            lines_changed = f.get("lines_changed", "")
            lines.append(f"| `{file_name}` | {change_type} | {lines_changed} |")
        lines.append("")

    # Overall Assessment
    verdict = review.get("overall_assessment", review.get("verdict", "COMMENT")).upper()
    if verdict == "APPROVE":
        lines.append("**✅ Overall Assessment: LOOKS GOOD**")
    elif "REQUEST" in verdict or "CHANGES" in verdict:
        lines.append("**⚠️ Overall Assessment: REQUEST CHANGES**")
    else:
        lines.append("**💬 Overall Assessment: COMMENTS**")
    lines.append("")

    # Summary
    summary = review.get("summary", "")
    if summary:
        lines.append(f"> {summary}")
        lines.append("")

    # Critical Issues (new detailed format)
    critical_issues = review.get("critical_issues", [])
    if critical_issues:
        lines.append("### 🔴 Critical Issues (Blocking)")
        lines.append("")
        for idx, issue in enumerate(critical_issues, 1):
            lines.extend(format_detailed_issue(idx, issue))

    # High Priority
    high_priority = review.get("high_priority", [])
    if high_priority:
        lines.append("### 🟠 High Priority")
        lines.append("")
        for idx, issue in enumerate(high_priority, 1):
            lines.extend(format_detailed_issue(idx, issue))

    # Medium Priority
    medium_priority = review.get("medium_priority", [])
    if medium_priority:
        lines.append("### 🟡 Medium Priority")
        lines.append("")
        for idx, issue in enumerate(medium_priority, 1):
            lines.extend(format_detailed_issue(idx, issue))

    # Suggestions
    suggestions = review.get("suggestions", [])
    if suggestions:
        lines.append("### 🔵 Suggestions")
        lines.append("")
        for idx, issue in enumerate(suggestions, 1):
            lines.extend(format_detailed_issue(idx, issue))

    # Backward compatibility: handle old "issues" format
    issues = review.get("issues", [])
    if issues and not (critical_issues or high_priority or medium_priority or suggestions):
        critical = [i for i in issues if i.get("severity") == "critical"]
        high = [i for i in issues if i.get("severity") == "high"]
        medium = [i for i in issues if i.get("severity") == "medium"]
        low = [i for i in issues if i.get("severity") == "low"]

        if critical:
            lines.append("### 🔴 Critical Issues")
            lines.append("")
            for idx, issue in enumerate(critical, 1):
                lines.extend(format_detailed_issue(idx, issue))

        if high:
            lines.append("### 🟠 High Priority")
            lines.append("")
            for idx, issue in enumerate(high, 1):
                lines.extend(format_detailed_issue(idx, issue))

        if medium:
            lines.append("### 🟡 Medium Priority")
            lines.append("")
            for idx, issue in enumerate(medium, 1):
                lines.extend(format_detailed_issue(idx, issue))

        if low:
            lines.append("### 🔵 Suggestions")
            lines.append("")
            for idx, issue in enumerate(low, 1):
                lines.extend(format_detailed_issue(idx, issue))

    # Positive Notes
    positive_notes = review.get("positive_notes", [])
    if positive_notes:
        lines.append("### ✅ Positive Notes")
        lines.append("")
        for note in positive_notes:
            lines.append(f"- {note}")
        lines.append("")

    # No issues found
    has_issues = critical_issues or high_priority or medium_priority or suggestions or issues
    if not has_issues and not review.get("raw_response"):
        lines.append("*No issues found. Great work!* 🎉")
        lines.append("")

    # Raw response fallback
    if review.get("raw_response"):
        lines.append("### Review Details")
        lines.append("")
        lines.append(review["raw_response"][:5000])
        lines.append("")

    # Footer
    model_info = COPILOT_MODEL or "claude-sonnet-4.5"
    lines.append("---")
    lines.append(f"*Model: {model_info} | Generated by [AI Code Review Extension](https://github.com/rs-001-ai/ai-code-review-extension-copilot)*")

    return "\n".join(lines)


def format_detailed_issue(idx: int, issue: dict) -> list:
    """Format a single issue with code snippets into markdown lines."""
    lines = []
    title = issue.get("title", "Issue")
    file_path = issue.get("file", "")
    line_num = issue.get("line", "")
    category = issue.get("category", "")

    # Issue header with location
    location = ""
    if file_path:
        location = f"`{file_path}"
        if line_num:
            location += f":{line_num}"
        location += "`"

    category_badge = f" [{category}]" if category else ""
    lines.append(f"**{idx}. {title}**{category_badge}")
    if location:
        lines.append(f"**File:** {location}")
    lines.append("")

    # Changed code snippet
    changed_code = issue.get("changed_code", "")
    if changed_code:
        lines.append("**Changed Code:**")
        lines.append("```")
        lines.append(changed_code[:500])  # Limit code length
        lines.append("```")
        lines.append("")

    # Problem description
    problem = issue.get("problem", issue.get("description", ""))
    if problem:
        lines.append(f"**Problem:** {problem}")
        lines.append("")

    # Impact
    impact = issue.get("impact", "")
    if impact:
        lines.append(f"**Impact:** {impact}")
        lines.append("")

    # Solution with code example
    solution = issue.get("solution", issue.get("suggestion", ""))
    if solution:
        lines.append(f"**Solution:** {solution}")
        lines.append("")

    lines.append("---")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Supported File Extensions
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".cs", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".hpp", ".rb", ".php", ".swift", ".kt", ".kts",
    ".scala", ".vue", ".svelte", ".dart", ".r", ".R", ".sql", ".sh",
    ".bash", ".ps1", ".psm1", ".yaml", ".yml", ".json", ".xml",
    ".tf", ".hcl", ".dockerfile", ".gradle", ".groovy",
}


def is_reviewable_file(path: str) -> bool:
    """Check if a file should be included in the review."""
    if not path:
        return False
    _, ext = os.path.splitext(path)
    return ext.lower() in SUPPORTED_EXTENSIONS


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def truncate_diff(diff: str, max_chars: int = 60000) -> str:
    """Truncate diff to stay within model context limits."""
    if len(diff) <= max_chars:
        return diff

    log.warning(f"Diff is {len(diff)} chars, truncating to {max_chars}")
    truncated = diff[:max_chars]
    # Try to cut at a line boundary
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars * 0.8:
        truncated = truncated[:last_newline]

    truncated += (
        "\n\n... [DIFF TRUNCATED - PR too large. Review covers first portion only.] ..."
    )
    return truncated


def main():
    """Main entry point for the code review task."""
    log.info("=" * 60)
    log.info("AI Code Review - Powered by GitHub Copilot")
    log.info("=" * 60)

    # Validate required inputs
    if not GITHUB_PAT:
        log.error("GitHub PAT is required. Set INPUT_GITHUB_PAT or the 'githubPat' task input.")
        sys.exit(1)

    if not ADO_TOKEN:
        log.error("Azure DevOps token is required. Enable 'Allow scripts to access OAuth token' "
                   "or set the 'adoPat' task input.")
        sys.exit(1)

    if not SYSTEM_PULLREQUEST_PULLREQUESTID:
        log.warning("No Pull Request ID found. This task should run as a PR build validation.")
        log.info("Skipping review - not a PR build.")
        return

    log.info(f"Organization: {SYSTEM_COLLECTIONURI}")
    log.info(f"Project: {SYSTEM_TEAMPROJECT}")
    log.info(f"Repository: {BUILD_REPOSITORY_NAME}")
    log.info(f"PR ID: {SYSTEM_PULLREQUEST_PULLREQUESTID}")
    log.info(f"Model: {COPILOT_MODEL or 'default (gpt-4o)'}")

    try:
        # Step 1: Get the PR diff
        log.info("Step 1: Fetching PR diff...")

        # Prefer git diff (faster, more complete) over API
        diff = get_diff_via_git()

        if not diff:
            log.info("Git diff unavailable, falling back to Azure DevOps API...")
            pr_details = get_pr_details()
            source_commit = pr_details.get("lastMergeSourceCommit", {}).get("commitId", "")
            target_commit = pr_details.get("lastMergeTargetCommit", {}).get("commitId", "")

            changes = get_pr_changes()
            log.info(f"Found {len(changes)} changed files")

            # Build diff from individual file changes
            diff_parts = []
            file_count = 0
            for change in changes:
                item = change.get("item", {})
                path = item.get("path", "")

                if not is_reviewable_file(path):
                    continue

                file_count += 1
                if file_count > MAX_FILES:
                    log.warning(f"Reached max files limit ({MAX_FILES}), skipping remaining")
                    break

                change_type = change.get("changeType", 0)
                # 1=add, 2=edit, 16=delete
                if change_type == 16:
                    diff_parts.append(f"\n--- a{path}\n+++ /dev/null\n[File deleted]")
                    continue

                content = get_file_content(path, source_commit)
                if content:
                    lines = content.split("\n")
                    if len(lines) > MAX_LINES_PER_FILE:
                        lines = lines[:MAX_LINES_PER_FILE]
                        lines.append(f"... [truncated at {MAX_LINES_PER_FILE} lines]")

                    type_label = "new file" if change_type == 1 else "modified"
                    diff_parts.append(
                        f"\n--- {'a' + path if change_type != 1 else '/dev/null'}"
                        f"\n+++ b{path}"
                        f"\n[{type_label}]\n"
                        + "\n".join(f"+{line}" for line in lines)
                    )

            diff = "\n".join(diff_parts)

        if not diff.strip():
            log.info("No reviewable changes found in this PR.")
            post_pr_comment(
                "## 🤖 AI Code Review (Powered by GitHub Copilot)\n\n"
                "No reviewable code changes detected in this PR. "
                "This may be because the changes are in unsupported file types."
            )
            return

        # Truncate if necessary
        diff = truncate_diff(diff)
        log.info(f"Diff size: {len(diff)} chars")

        # Step 2: Run GitHub Models API review
        log.info("Step 2: Running GitHub Models API code review...")
        raw_response = run_copilot_review(diff)

        if not raw_response:
            raise RuntimeError("GitHub Models API returned empty response")

        log.debug(f"Raw response:\n{raw_response[:500]}...")

        # Step 3: Parse and format the review
        log.info("Step 3: Parsing review results...")
        review = parse_review_response(raw_response)
        comment = format_review_comment(review)

        # Step 4: Post comment to PR
        log.info("Step 4: Posting review to PR...")
        post_pr_comment(comment)

        # Summary
        issue_count = len(review.get("issues", []))
        verdict = review.get("verdict", "COMMENT")
        log.info(f"Review complete: {verdict} with {issue_count} issue(s) found")
        log.info("=" * 60)

    except Exception as e:
        log.error(f"Review failed: {e}", exc_info=DEBUG)

        if CONTINUE_ON_ERROR:
            log.warning("continueOnError is enabled, pipeline will not fail")
            try:
                post_pr_comment(
                    "## 🤖 AI Code Review (Powered by GitHub Models API)\n\n"
                    f"⚠️ Review could not be completed: `{str(e)[:200]}`\n\n"
                    "This may be due to GitHub PAT permissions, API availability, "
                    "or the PR being too large. Check the pipeline logs for details."
                )
            except Exception:
                log.error("Could not post error comment to PR")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
