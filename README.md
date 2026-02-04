# AI Code Review for Azure DevOps (Powered by GitHub Copilot)

Automatically review Pull Requests using **GitHub Copilot** models. Get instant feedback on security vulnerabilities, performance issues, and best practices — no OpenAI API key required.

> **v2.0 Migration:** This version replaces OpenAI API with GitHub Copilot. If you're upgrading from v1.x, see the [Migration Guide](#migrating-from-v1-openai) below.

## Features

- **GitHub Copilot Powered** — Uses your existing Copilot subscription, no separate API costs
- **Multi-Model Support** — Choose from Claude Sonnet 4.5, GPT-5.1, Gemini 3 Pro, and more
- **Automated PR Reviews** — Runs automatically on every Pull Request
- **Multi-Language Support** — Python, JavaScript/TypeScript, C#, Java, Go, Rust, C++, and more
- **Framework-Aware** — React, Vue, Angular, FastAPI, Flask, Express, Spring, ASP.NET
- **Security Analysis** — OWASP Top 10, injection vulnerabilities, authentication issues
- **Performance Review** — Algorithm complexity, database queries, memory management
- **Custom Prompts** — Tailor review focus to your team's needs
- **Inline Comments** — Posts structured review comments directly on your PR

## Quick Start

### 1. Install the Extension

Install from the [Visual Studio Marketplace](https://marketplace.visualstudio.com/items?itemName=RachitSinghal.code-review-bot).

### 2. Create a GitHub PAT

1. Go to [GitHub Settings > Developer Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. Generate a new **Fine-grained** token:
   - **Repository access:** Public
   - **Permission:** Copilot Requests
3. Store as a secret variable `GITHUB_PAT` in your Azure DevOps pipeline

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
    githubPat: $(GITHUB_PAT)
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

### 4. Enable OAuth Token

In your pipeline settings, ensure **"Allow scripts to access the OAuth token"** is enabled.

## Configuration Options

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `githubPat` | Yes | - | GitHub PAT with Copilot access |
| `adoPat` | No | System.AccessToken | Azure DevOps PAT (for on-prem) |
| `copilotModel` | No | `claude-sonnet-4.5` | AI model for review |
| `maxFiles` | No | `50` | Max files to review per PR |
| `maxLinesPerFile` | No | `1000` | Truncate files larger than this |
| `customPrompt` | No | - | Custom review instructions |
| `promptFile` | No | - | Path to prompt file (.txt) |
| `debug` | No | `false` | Enable verbose logging |
| `continueOnError` | No | `true` | Don't fail pipeline on review error |

### Available Models

| Model | Speed | Quality | Notes |
|-------|-------|---------|-------|
| `claude-sonnet-4.5` | Fast | High | Default — best balance |
| `claude-haiku-4.5` | Fastest | Good | Best for large PRs |
| `claude-opus-4.5` | Slower | Highest | Most thorough reviews |
| `gpt-5.1-codex` | Fast | High | OpenAI's coding model |
| `gpt-5.1-codex-mini` | Fastest | Good | Lighter, faster |
| `gpt-4.1` | Fast | High | Proven, reliable |
| `gemini-3-pro-preview` | Fast | High | Google's latest |

## Custom Review Prompts

### Inline Prompt

```yaml
- task: AICodeReview@2
  inputs:
    githubPat: $(GITHUB_PAT)
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
    githubPat: $(GITHUB_PAT)
    promptFile: '$(Build.SourcesDirectory)/.copilot/review-prompt.txt'
```

## Supported Languages

| Language | Review Coverage |
|----------|----------------|
| Python | PEP 8, type hints, async patterns, testing |
| JavaScript/TypeScript | Modern ES, async/await, error handling |
| C#/.NET | LINQ, async/await, null safety, DI, .NET 8 patterns |
| Java | Streams, Optional, Spring patterns |
| Go | Error handling, concurrency, interfaces |
| Rust | Ownership, error handling, unsafe code |
| C/C++ | Memory management, RAII, modern C++ |

## Supported Frameworks

| Framework | Review Coverage |
|-----------|----------------|
| React | Hooks, performance, accessibility |
| Vue | Composition API, reactivity, Pinia |
| Angular | Signals, standalone components, RxJS |
| FastAPI | Async, Pydantic, dependency injection |
| Flask | Blueprints, error handling |
| Express | Middleware, error handling, security |
| Spring Boot | DI, transactions, JPA |
| ASP.NET Core | DI, async, minimal APIs, Row-Level Security |

## Review Output

The task posts a structured review comment on your PR:

```markdown
## AI Code Review (Powered by GitHub Copilot)

Overall Assessment: CHANGES REQUESTED

> Found 2 security issues and 1 performance concern in the authentication module.

### Critical Issues

**1. SQL Injection Vulnerability** [security] `src/repository.py:45`
  - **Problem**: String concatenation used in SQL query
  - **Suggestion**: Use parameterized queries with SqlParameter

### Medium Priority

**1. Consider async/await** [performance] `src/service.cs:23`
  - **Problem**: Synchronous database calls blocking thread pool
  - **Suggestion**: Use async overloads with await for I/O operations
```

## Migrating from v1 (OpenAI)

### What Changed

| v1 (OpenAI) | v2 (GitHub Copilot) |
|-------------|-------------------|
| `openaiApiKey` | `githubPat` |
| `openaiModel: 'gpt-5.2-codex'` | `copilotModel: 'claude-sonnet-4.5'` |
| OpenAI API costs | Included with Copilot subscription |
| Direct API calls | Copilot CLI / GitHub Models API |

### Migration Steps

1. Remove `OPENAI_API_KEY` from your pipeline variables
2. Add `GITHUB_PAT` (GitHub PAT with Copilot Requests permission)
3. Update your pipeline YAML:

```yaml
# BEFORE (v1)
- task: AICodeReview@1
  inputs:
    openaiApiKey: $(OPENAI_API_KEY)
    openaiModel: 'gpt-5.2-codex'

# AFTER (v2)
- task: AICodeReview@2
  inputs:
    githubPat: $(GITHUB_PAT)
    copilotModel: 'claude-sonnet-4.5'  # optional
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

4. Add `fetchDepth: 0` to your checkout step (recommended for better diffs)

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌────────────────┐
│   PR Created     │────▶│  Pipeline Runs   │────▶│  Fetch Diff    │
│  (Azure DevOps)  │     │  (Build Agent)   │     │  (git / API)   │
└─────────────────┘     └─────────────────┘     └───────┬────────┘
                                                        │
                        ┌─────────────────┐     ┌───────▼────────┐
                        │ Post PR Comment  │◀────│ Copilot CLI    │
                        │ (ADO REST API)   │     │ Reviews Diff   │
                        └─────────────────┘     └────────────────┘
```

1. **PR trigger** — Branch policy triggers the review pipeline
2. **Fetch diff** — Gets code changes via `git diff` (preferred) or Azure DevOps API
3. **Copilot review** — Sends diff to GitHub Copilot CLI with review prompt
4. **Post results** — Formats findings and posts as a PR comment thread

## Privacy & Security

- Code is sent to GitHub Copilot for analysis (same as using Copilot in your IDE)
- GitHub PAT is handled as a secret and never logged
- No code is stored by this extension beyond the pipeline run
- Review results are posted only to your PR

## Troubleshooting

### "GitHub Copilot CLI not found"

- **Linux**: The task auto-installs via `https://gh.io/copilot-install`. Ensure the agent has internet access and `curl`/`bash` are available.
- **Windows**: Requires `winget`. MS-hosted agents have this by default.

### Authentication errors

- Verify your GitHub PAT has **Copilot Requests** permission
- If your GitHub account is in an organization, ensure the admin has enabled **Copilot CLI** under GitHub Policies > Copilot
- Ensure **"Allow scripts to access OAuth token"** is enabled in the pipeline

### Empty review or no comments

- Add `fetchDepth: 0` to the checkout step for complete git history
- Check pipeline logs for Copilot CLI output
- For very large PRs, try setting a lower `maxFiles` value or use `claude-haiku-4.5` for better handling of large context

### Timeout errors

- Large PRs may take longer. The default timeout is 10 minutes.
- Consider using `claude-haiku-4.5` for faster reviews on large PRs
- Break large PRs into smaller, focused changes

### Build Service permissions

If using `System.AccessToken`, the Build Service identity needs "Contribute to pull requests" permission:

1. Go to **Repos** > **Manage repositories** > **Security**
2. Find **"[Project] Build Service ([Org])"**
3. Set **"Contribute to pull requests"** to **Allow**

## Support

- [GitHub Issues](https://github.com/rs-001-ai/ai-code-review-extension-copilot/issues)
- [Documentation](https://github.com/rs-001-ai/ai-code-review-extension-copilot)

## License

MIT License - See [LICENSE](LICENSE) for details.
