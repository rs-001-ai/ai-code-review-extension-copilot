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
# Default Review Prompt
# ---------------------------------------------------------------------------

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
    """Build the full review prompt including the diff."""
    # Use custom prompt if provided
    if CUSTOM_PROMPT:
        prompt = CUSTOM_PROMPT
    elif PROMPT_FILE and os.path.isfile(PROMPT_FILE):
        with open(PROMPT_FILE, "r") as f:
            prompt = f.read()
    else:
        prompt = DEFAULT_REVIEW_PROMPT

    return f"{prompt}\n\n---\n\nHere are the code changes to review:\n\n```diff\n{diff}\n```"


def run_copilot_review(diff: str, cli_command: str) -> str:
    """
    Send the diff to GitHub Copilot CLI for review.

    The Copilot CLI supports piped input and non-interactive mode.
    We write the full prompt (instructions + diff) to a temp file and
    pass it to the CLI.
    """
    full_prompt = build_review_prompt(diff)

    # Write prompt to temp file (avoids shell escaping issues with large diffs)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, prefix="copilot_review_"
    ) as tmp:
        tmp.write(full_prompt)
        prompt_file = tmp.name

    log.info(f"Review prompt written to {prompt_file} ({len(full_prompt)} chars)")

    try:
        env = {
            **os.environ,
            "GH_TOKEN": GITHUB_PAT,
            "GITHUB_TOKEN": GITHUB_PAT,
            "NO_COLOR": "1",  # Disable color codes in output
        }

        # Build the command based on which CLI variant is available
        if cli_command == "gh-copilot":
            # Using the gh copilot extension (deprecated but functional)
            cmd = ["gh", "copilot", "suggest", "-t", "shell"]
            # gh copilot doesn't support file-based prompts well,
            # so we use a different approach: pipe via stdin
            log.info("Using gh copilot extension for review...")
            with open(prompt_file, "r") as f:
                prompt_content = f.read()

            result = subprocess.run(
                ["gh", "api", "copilot/chat/completions",
                 "--method", "POST",
                 "--input", "-"],
                input=json.dumps({
                    "model": COPILOT_MODEL or "claude-sonnet-4.5",
                    "messages": [
                        {"role": "system", "content": "You are an expert code reviewer."},
                        {"role": "user", "content": prompt_content}
                    ]
                }),
                capture_output=True, text=True, timeout=600, env=env
            )
        else:
            # Using the standalone Copilot CLI
            cmd = [cli_command]

            # Build model flag if specified
            model_args = []
            if COPILOT_MODEL:
                model_args = ["--model", COPILOT_MODEL]

            log.info(f"Running Copilot CLI: {cli_command} "
                     f"(model: {COPILOT_MODEL or 'default'})...")

            # Read the prompt and pipe it to copilot CLI
            with open(prompt_file, "r") as f:
                prompt_content = f.read()

            # Use copilot with -p (prompt) flag for non-interactive mode
            result = subprocess.run(
                [cli_command, "-p", prompt_content] + model_args,
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
                cwd=os.environ.get("BUILD_SOURCESDIRECTORY", os.getcwd())
            )

        if result.returncode != 0:
            log.error(f"Copilot CLI exited with code {result.returncode}")
            log.error(f"stderr: {result.stderr}")

            # Fallback: try using the gh api approach for Copilot chat
            log.info("Trying fallback via gh api copilot endpoint...")
            return run_copilot_via_gh_api(full_prompt, env)

        output = result.stdout.strip()
        if not output:
            log.warning("Copilot CLI returned empty output, trying stderr...")
            output = result.stderr.strip()

        log.info(f"Copilot review received ({len(output)} chars)")
        return output

    finally:
        try:
            os.unlink(prompt_file)
        except OSError:
            pass


def run_copilot_via_gh_api(prompt: str, env: dict) -> str:
    """
    Fallback: Use the GitHub Copilot Chat Completions API via `gh api`.
    This uses the GitHub REST API endpoint for Copilot chat.
    """
    model = COPILOT_MODEL or "claude-sonnet-4.5"

    payload = json.dumps({
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
        ]
    })

    # Write payload to temp file to avoid argument length limits
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="copilot_payload_"
    ) as tmp:
        tmp.write(payload)
        payload_file = tmp.name

    try:
        result = subprocess.run(
            ["gh", "api",
             "--method", "POST",
             "-H", "Accept: application/json",
             "models/chat/completions",
             "--input", payload_file],
            capture_output=True, text=True, timeout=600, env=env
        )

        if result.returncode != 0:
            log.error(f"gh api fallback failed: {result.stderr}")
            raise RuntimeError(f"All Copilot CLI methods failed. stderr: {result.stderr}")

        response = json.loads(result.stdout)
        choices = response.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return result.stdout

    finally:
        try:
            os.unlink(payload_file)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Review Parsing & Formatting
# ---------------------------------------------------------------------------

def parse_review_response(raw_response: str) -> dict:
    """Parse the JSON review response from Copilot."""
    # Try to extract JSON from the response (it may be wrapped in markdown)
    text = raw_response.strip()

    # Remove markdown code fences if present
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("Could not parse JSON from Copilot response, treating as raw text")
        return {
            "summary": "Review completed (raw response - could not parse structured output)",
            "verdict": "COMMENT",
            "issues": [],
            "raw_response": raw_response,
        }


def format_review_comment(review: dict) -> str:
    """Format the review into a markdown comment for Azure DevOps."""
    lines = []

    # Header
    lines.append("## 🤖 AI Code Review (Powered by GitHub Copilot)")
    lines.append("")

    # Verdict badge
    verdict = review.get("verdict", "COMMENT").upper()
    if verdict == "APPROVE":
        lines.append("**✅ Overall Assessment: LOOKS GOOD**")
    elif verdict == "REQUEST_CHANGES":
        lines.append("**⚠️ Overall Assessment: CHANGES REQUESTED**")
    else:
        lines.append("**💬 Overall Assessment: COMMENTS**")
    lines.append("")

    # Summary
    summary = review.get("summary", "")
    if summary:
        lines.append(f"> {summary}")
        lines.append("")

    # Issues
    issues = review.get("issues", [])
    if issues:
        # Group by severity
        critical = [i for i in issues if i.get("severity") == "critical"]
        high = [i for i in issues if i.get("severity") == "high"]
        medium = [i for i in issues if i.get("severity") == "medium"]
        low = [i for i in issues if i.get("severity") == "low"]

        if critical:
            lines.append("### 🔴 Critical Issues")
            lines.append("")
            for idx, issue in enumerate(critical, 1):
                lines.extend(format_issue(idx, issue))
            lines.append("")

        if high:
            lines.append("### 🟠 High Priority")
            lines.append("")
            for idx, issue in enumerate(high, 1):
                lines.extend(format_issue(idx, issue))
            lines.append("")

        if medium:
            lines.append("### 🟡 Medium Priority")
            lines.append("")
            for idx, issue in enumerate(medium, 1):
                lines.extend(format_issue(idx, issue))
            lines.append("")

        if low:
            lines.append("### 🔵 Suggestions")
            lines.append("")
            for idx, issue in enumerate(low, 1):
                lines.extend(format_issue(idx, issue))
            lines.append("")

    elif not review.get("raw_response"):
        lines.append("*No issues found. Great work!* 🎉")
        lines.append("")

    # Raw response fallback
    if review.get("raw_response"):
        lines.append("### Review Details")
        lines.append("")
        lines.append(review["raw_response"][:5000])  # Truncate very long responses
        lines.append("")

    # Footer
    model_info = COPILOT_MODEL or "default"
    lines.append("---")
    lines.append(f"*Reviewed by GitHub Copilot (model: {model_info}) | "
                 f"[AI Code Review Extension](https://github.com/rs-001-ai/ai-code-review-extension)*")

    return "\n".join(lines)


def format_issue(idx: int, issue: dict) -> list:
    """Format a single issue into markdown lines."""
    lines = []
    title = issue.get("title", "Issue")
    file_path = issue.get("file", "")
    line_num = issue.get("line", "")
    category = issue.get("category", "")

    location = ""
    if file_path:
        location = f" `{file_path}"
        if line_num:
            location += f":{line_num}"
        location += "`"

    category_badge = ""
    if category:
        category_badge = f" [{category}]"

    lines.append(f"**{idx}. {title}**{category_badge}{location}")

    description = issue.get("description", "")
    if description:
        lines.append(f"  - **Problem**: {description}")

    suggestion = issue.get("suggestion", "")
    if suggestion:
        lines.append(f"  - **Suggestion**: {suggestion}")

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

def truncate_diff(diff: str, max_chars: int = 80000) -> str:
    """Truncate diff to stay within Copilot's context window."""
    if len(diff) <= max_chars:
        return diff

    log.warning(f"Diff is {len(diff)} chars, truncating to {max_chars}")
    truncated = diff[:max_chars]
    # Try to cut at a line boundary
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars * 0.8:
        truncated = truncated[:last_newline]

    truncated += (
        "\n\n... [DIFF TRUNCATED - PR is too large for full review. "
        "Consider breaking into smaller PRs.] ..."
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
    log.info(f"Model: {COPILOT_MODEL or 'default (claude-sonnet-4.5)'}")

    try:
        # Step 1: Install/verify Copilot CLI
        log.info("Step 1: Verifying GitHub Copilot CLI...")
        cli_command = install_copilot_cli()
        log.info(f"Copilot CLI ready: {cli_command}")

        # Step 2: Get the PR diff
        log.info("Step 2: Fetching PR diff...")

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

        # Step 3: Run Copilot review
        log.info("Step 3: Running GitHub Copilot code review...")
        raw_response = run_copilot_review(diff, cli_command)

        if not raw_response:
            raise RuntimeError("Copilot returned empty response")

        log.debug(f"Raw response:\n{raw_response[:500]}...")

        # Step 4: Parse and format the review
        log.info("Step 4: Parsing review results...")
        review = parse_review_response(raw_response)
        comment = format_review_comment(review)

        # Step 5: Post comment to PR
        log.info("Step 5: Posting review to PR...")
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
                    "## 🤖 AI Code Review (Powered by GitHub Copilot)\n\n"
                    f"⚠️ Review could not be completed: `{str(e)[:200]}`\n\n"
                    "This may be due to Copilot CLI availability, authentication issues, "
                    "or the PR being too large. Check the pipeline logs for details."
                )
            except Exception:
                log.error("Could not post error comment to PR")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
