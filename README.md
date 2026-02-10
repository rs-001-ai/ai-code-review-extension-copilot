# AI Code Review for Azure DevOps (Powered by GitHub Copilot)

Automatically review Pull Requests using **GitHub Copilot CLI**. Get instant, language-aware feedback on security vulnerabilities, performance issues, and best practices — powered by Claude Sonnet 4.5.

## Features

- **GitHub Copilot CLI** — Reviews code using Claude, GPT-5, and Gemini models via your Copilot subscription
- **Skill-Based Analysis** — Automatically detects languages and frameworks, loads specialized review rules
- **Multi-Model Support** — Claude Sonnet/Opus/Haiku 4.5, GPT-5.x Codex, Gemini 3 Pro
- **Automated PR Reviews** — Runs automatically on every Pull Request
- **20+ Languages** — Python, JavaScript/TypeScript, C#, Java, Go, Rust, C++, and more
- **Framework-Aware** — React, Vue, Angular, FastAPI, Flask, Express, Spring, ASP.NET
- **Security Analysis** — OWASP Top 10, injection vulnerabilities, crypto weaknesses, auth issues
- **Performance Review** — Algorithm complexity, database queries, memory management, async patterns
- **Large PR Support** — Handles diffs up to 400K chars (~115K tokens) using Claude's 200K context
- **Custom Prompts** — Tailor review focus to your team's needs
- **Structured Comments** — Posts categorized review findings directly on your PR
- **API Fallback** — Falls back to GitHub Models API (GPT-5) if Copilot CLI is unavailable

## Quick Start

### 1. Install the Extension

Install from the [Visual Studio Marketplace](https://marketplace.visualstudio.com/items?itemName=RachitSinghal.copilot-code-review-bot).

### 2. Create a GitHub Fine-Grained PAT

> **Important**: You must use a **Fine-Grained Personal Access Token** (`github_pat_*`). Classic PATs (`ghp_*`) do not have Copilot scopes and will not work.

1. Go to [GitHub Settings > Fine-grained tokens](https://github.com/settings/personal-access-tokens/new)
2. Set a name (e.g., "ADO Copilot Code Review") and expiration
3. Under **Permissions**, enable:
   - **Copilot Requests** — Read and Write (required for Copilot CLI)
   - **Models** — Read (required for API fallback)
4. Generate the token (it will start with `github_pat_`)
5. Store as a secret variable `GitHubPAT` in your Azure DevOps pipeline

### 3. Add to Your Pipeline

```yaml
trigger: none

pr:
  branches:
    include:
      - main
      - develop

pool:
  vmImage: 'ubuntu-latest'

steps:
- checkout: self
  fetchDepth: 0  # Required for full diff

- task: AICodeReview@2
  inputs:
    githubPat: $(GitHubPAT)
    copilotModel: 'claude-sonnet-4.5'
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

### 4. Enable OAuth Token

In your pipeline settings, ensure **"Allow scripts to access the OAuth token"** is enabled. This is required for posting review comments to the PR.

## Configuration Options

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `githubPat` | Yes | - | GitHub Fine-Grained PAT with Copilot + Models permissions |
| `adoPat` | No | System.AccessToken | Azure DevOps PAT (for on-prem / Azure DevOps Server) |
| `copilotModel` | No | `claude-sonnet-4.5` | AI model for review (see Available Models) |
| `maxFiles` | No | `50` | Max files to review per PR |
| `maxLinesPerFile` | No | `1000` | Truncate files larger than this |
| `customPrompt` | No | - | Custom review instructions (overrides skill-based prompt) |
| `promptFile` | No | - | Path to prompt file (.txt) |
| `debug` | No | `false` | Enable verbose logging |
| `continueOnError` | No | `true` | Don't fail pipeline on review error |

### Available Models

All models are accessed via **GitHub Copilot CLI** using your Copilot subscription:

| Model | Speed | Quality | Best For |
|-------|-------|---------|----------|
| `claude-sonnet-4.5` | Fast | High | **Default** — best balance for code review |
| `claude-opus-4.5` | Slower | Highest | Most thorough analysis (3x Premium requests) |
| `claude-haiku-4.5` | Fastest | Good | Large PRs, quick feedback (0.33x Premium requests) |
| `gpt-5.1-codex` | Fast | High | OpenAI code specialist |
| `gpt-5.1` | Fast | High | OpenAI flagship |
| `gpt-5` | Fast | High | OpenAI previous generation |
| `gemini-3-pro` | Fast | High | Google latest |

> **Note**: Model availability depends on your GitHub Copilot subscription tier (Individual, Business, Enterprise).

## Skill-Based Review System

The extension uses a **skill-based prompt system** that automatically adapts to the code being reviewed:

1. **Language Detection** — Analyzes file extensions in the diff to load language-specific rules
2. **Framework Detection** — Scans diff content for framework patterns (React, Angular, ASP.NET, etc.)
3. **Cross-Cutting Concerns** — Always loads security, architecture, and performance review guidelines

### Skill Files Loaded Per Review

| Skill | When Loaded | Coverage |
|-------|-------------|----------|
| `SKILL.md` | Always | Core review process, output format, PR scope rules |
| `csharp.md` | `.cs` files | LINQ, async/await, null safety, DI, .NET patterns |
| `python.md` | `.py` files | PEP 8, type hints, async patterns, testing |
| `javascript.md` | `.js/.ts/.jsx/.tsx` files | Modern ES, async/await, error handling |
| `java.md` | `.java/.kt` files | Streams, Optional, Spring patterns |
| `go.md` | `.go` files | Error handling, concurrency, interfaces |
| `rust.md` | `.rs` files | Ownership, error handling, unsafe code |
| `cpp.md` | `.c/.cpp/.h` files | Memory management, RAII, modern C++ |
| `frontend.md` | React/Vue/Angular detected | Hooks, performance, accessibility, state management |
| `backend.md` | FastAPI/Express/Spring detected | API design, middleware, auth patterns |
| `security.md` | Always | OWASP Top 10, injection, crypto, auth, data exposure |
| `architecture.md` | Always | SOLID, design patterns, dependencies |
| `performance.md` | Always | Complexity, queries, memory, caching |

### Custom Prompts Override Skills

When you provide a `customPrompt` or `promptFile`, it takes priority over the skill-based system:

```yaml
- task: AICodeReview@2
  inputs:
    githubPat: $(GitHubPAT)
    copilotModel: 'claude-sonnet-4.5'
    customPrompt: |
      Review this code focusing only on:
      - Security vulnerabilities (OWASP Top 10)
      - .NET 8 migration best practices
      - BACnet protocol handling patterns
      - Async/await correctness
      Keep comments concise and actionable.
```

### Prompt File

Create a `.copilot/review-prompt.txt` in your repo:

```yaml
- task: AICodeReview@2
  inputs:
    githubPat: $(GitHubPAT)
    promptFile: '$(Build.SourcesDirectory)/.copilot/review-prompt.txt'
```

## Supported Languages

| Language | Extensions | Review Coverage |
|----------|-----------|----------------|
| Python | `.py` | PEP 8, type hints, async patterns, testing |
| JavaScript/TypeScript | `.js`, `.ts`, `.jsx`, `.tsx` | Modern ES, async/await, error handling |
| C#/.NET | `.cs` | LINQ, async/await, null safety, DI, .NET 8 patterns |
| Java/Kotlin | `.java`, `.kt` | Streams, Optional, Spring patterns |
| Go | `.go` | Error handling, concurrency, interfaces |
| Rust | `.rs` | Ownership, error handling, unsafe code |
| C/C++ | `.c`, `.cpp`, `.h` | Memory management, RAII, modern C++ |
| Ruby | `.rb` | Reviewed with general best practices |
| PHP | `.php` | Reviewed with general best practices |
| Swift | `.swift` | Reviewed with general best practices |
| SQL | `.sql` | Injection, query optimization |
| Shell | `.sh`, `.bash`, `.ps1` | Command injection, quoting |
| Config | `.yaml`, `.json`, `.xml`, `.tf` | Secrets exposure, misconfiguration |

## Supported Frameworks

| Framework | Detection | Review Coverage |
|-----------|-----------|----------------|
| React | `react`, `.jsx`, `.tsx` | Hooks, performance, accessibility |
| Vue | `vue`, `.vue` | Composition API, reactivity, Pinia |
| Angular | `@angular` | Signals, standalone components, RxJS |
| Svelte | `svelte`, `.svelte` | Reactivity, accessibility |
| FastAPI | `fastapi` | Async, Pydantic, dependency injection |
| Flask | `flask` | Blueprints, error handling |
| Express | `express` | Middleware, error handling, security |
| Spring Boot | `spring` | DI, transactions, JPA |
| ASP.NET Core | `asp.net`, `webapi` | DI, async, minimal APIs, Row-Level Security |

## Review Output

The task posts a structured review comment on your PR with categorized findings:

```
## AI Code Review (Powered by GitHub Copilot)

**PR/Change Description**: Adds StringHelper utility class with password hashing and validation

### Files Reviewed

| File | Change Type | Lines Changed |
|------|-------------|---------------|
| `src/Utilities/StringHelper.cs` | Added | +79/-0 |

**Overall Assessment: REQUEST CHANGES**

> Found 2 critical security issues and 1 logic bug in the utility class.

### Critical Issues (Blocking)

**1. Weak Cryptographic Algorithm** [security]
**File:** `StringHelper.cs:17`

**Problem:** MD5 is cryptographically broken and unsuitable for password hashing.
**Solution:** Use PasswordHasher<T> from Microsoft.AspNetCore.Identity.

---

### High Priority

**1. Null Reference Exception** [logic]
**File:** `StringHelper.cs:37`

**Problem:** Code checks if email is null, then immediately dereferences it.
**Solution:** Return false for null values before accessing .Contains().

---

### Suggestions

**1. Inadequate Email Validation** [best-practice]
**File:** `StringHelper.cs:39`

**Problem:** Only checks for '@' symbol. Use EmailAddressAttribute for proper validation.

---

*Model: claude-sonnet-4.5 | Generated by AI Code Review Extension*
```

## How It Works

```
                                ┌──────────────────────────┐
                                │    GitHub Copilot CLI     │
                                │  (Claude Sonnet 4.5)     │
                                └────────────┬─────────────┘
                                             │
┌────────────┐    ┌────────────┐    ┌────────▼───────┐    ┌────────────────┐
│ PR Created  │───>│  Pipeline  │───>│  Fetch Diff    │───>│ Skill-Based    │
│ (Azure      │    │  Runs      │    │  (git diff)    │    │ Prompt Builder │
│  DevOps)    │    │            │    │                │    │                │
└────────────┘    └────────────┘    └────────────────┘    └───────┬────────┘
                                                                  │
                  ┌────────────────┐    ┌─────────────────┐       │
                  │ Post PR Comment │<───│ Parse & Format  │<──────┘
                  │ (ADO REST API)  │    │ Review Results  │
                  └────────────────┘    └─────────────────┘
```

### Review Flow

1. **PR trigger** — Branch policy triggers the review pipeline
2. **Fetch diff** — Gets code changes via `git diff` (preferred) or Azure DevOps REST API
3. **Detect context** — Identifies languages, frameworks from file extensions and diff content
4. **Build prompt** — Loads relevant skill files (SKILL.md + language + framework + security/arch/perf)
5. **Copilot review** — Sends prompt + diff to GitHub Copilot CLI with the selected model
6. **Fallback** — If Copilot CLI fails, falls back to GitHub Models API with GPT-5
7. **Parse results** — Extracts structured JSON review from the AI response
8. **Post comment** — Formats findings and posts as a categorized PR comment thread

## Architecture

### Primary: GitHub Copilot CLI

The extension installs and uses the **GitHub Copilot CLI** (`@github/copilot` npm package) for code review. This provides:

- Access to Claude, GPT, and Gemini models via your Copilot subscription
- Large context windows (Claude Sonnet 4.5: 200K tokens)
- No per-token API billing — uses your Copilot Premium requests

### Fallback: GitHub Models API

If Copilot CLI is unavailable (e.g., auth issues, installation failure), the extension falls back to the **GitHub Models API** (`models.github.ai/inference`) using GPT-5 with a 4K token input limit.

## Privacy & Security

- Code is sent to GitHub Copilot for analysis (same as using Copilot in your IDE)
- GitHub PAT is handled as a secret and never logged (only first/last 4 chars shown in debug)
- No code is stored by this extension beyond the pipeline run
- Review results are posted only to your PR
- All API communication uses HTTPS

## Troubleshooting

### "No authentication information found"

This is the most common error. It means the Copilot CLI cannot authenticate with your GitHub token.

**Cause**: You are using a **classic PAT** (`ghp_*`). The Copilot CLI only accepts:
- **Fine-Grained Personal Access Tokens** (`github_pat_*`)
- **OAuth Tokens** (`gho_*`)

**Fix**:
1. Go to [GitHub Settings > Fine-grained tokens](https://github.com/settings/personal-access-tokens/new)
2. Create a new token with **Copilot Requests** (Read & Write) and **Models** (Read) permissions
3. Update the `GitHubPAT` pipeline variable with the new `github_pat_*` token

### "gh auth login failed: missing required scope 'repo'"

This is expected when using a fine-grained PAT without `repo` scope. The extension will still work — Copilot CLI authenticates via the `COPILOT_GITHUB_TOKEN` environment variable, not through `gh auth`.

### "GitHub Copilot CLI not found"

The task auto-installs the Copilot CLI via `npm install -g @github/copilot@latest`. If this fails:

- **Linux agents**: Ensure the agent has internet access and `npm` is available
- **Windows agents**: Ensure `npm` is in PATH
- **Self-hosted agents**: Pre-install with `npm install -g @github/copilot@latest`

### Empty review or no comments

- Add `fetchDepth: 0` to the checkout step for complete git history
- Check pipeline logs for Copilot CLI output
- Enable `debug: true` to see detailed prompt and response info
- For very large PRs (700K+ chars), the diff is truncated to 400K chars — consider breaking into smaller PRs

### Timeout errors

- Large PRs may take longer. The Copilot CLI timeout is 5 minutes.
- Consider using `claude-haiku-4.5` for faster reviews on large PRs
- Break large PRs into smaller, focused changes

### Build Service permissions

If using `System.AccessToken`, the Build Service identity needs "Contribute to pull requests" permission:

1. Go to **Project Settings** > **Repos** > **Repositories** > your repo > **Security**
2. Find **"[Project] Build Service ([Org])"**
3. Set **"Contribute to pull requests"** to **Allow**

### JSON parse errors in review

If you see "JSON parse error" in the logs, the AI response was truncated or malformed. The extension has built-in recovery:
- Attempts to repair truncated JSON by adding missing brackets
- Falls back to regex extraction of issues from the raw response
- Posts whatever findings it could extract

## Support

- [GitHub Issues](https://github.com/rs-001-ai/ai-code-review-extension-copilot/issues)
- [Documentation](https://github.com/rs-001-ai/ai-code-review-extension-copilot)

## License

MIT License - See [LICENSE](LICENSE) for details.
