# Local Test Script for AI Code Review Extension
# Usage: .\test-local.ps1 -GitHubPat "your-github-pat" -AdoOrg "your-org" -AdoProject "your-project" -RepoId "your-repo-id" -PrId "123"

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubPat,

    [Parameter(Mandatory=$false)]
    [string]$AdoPat = "",

    [Parameter(Mandatory=$true)]
    [string]$AdoOrg,

    [Parameter(Mandatory=$true)]
    [string]$AdoProject,

    [Parameter(Mandatory=$true)]
    [string]$RepoId,

    [Parameter(Mandatory=$true)]
    [string]$PrId,

    [Parameter(Mandatory=$false)]
    [string]$CopilotModel = "claude-sonnet-4.5",

    [Parameter(Mandatory=$false)]
    [string]$MaxFiles = "50",

    [Parameter(Mandatory=$false)]
    [string]$MaxLinesPerFile = "1000",

    [Parameter(Mandatory=$false)]
    [switch]$Debug
)

Write-Host "================================" -ForegroundColor Cyan
Write-Host "AI Code Review - Local Test" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Set Azure DevOps Task input environment variables
$env:INPUT_GITHUBPAT = $GitHubPat
$env:INPUT_ADOPAT = $AdoPat
$env:INPUT_COPILOTMODEL = $CopilotModel
$env:INPUT_MAXFILES = $MaxFiles
$env:INPUT_MAXLINESPERFILE = $MaxLinesPerFile
$env:INPUT_DEBUG = if ($Debug) { "true" } else { "false" }
$env:INPUT_CONTINUEONERROR = "true"

# Set Azure DevOps system environment variables
$env:SYSTEM_TEAMFOUNDATIONCOLLECTIONURI = "https://dev.azure.com/$AdoOrg/"
$env:SYSTEM_TEAMPROJECTID = $AdoProject
$env:BUILD_REPOSITORY_ID = $RepoId
$env:SYSTEM_PULLREQUEST_PULLREQUESTID = $PrId
$env:SYSTEM_ACCESSTOKEN = $AdoPat

# GitHub token for Copilot CLI
$env:GH_TOKEN = $GitHubPat
$env:GITHUB_TOKEN = $GitHubPat

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  ADO Org:        $AdoOrg"
Write-Host "  ADO Project:    $AdoProject"
Write-Host "  Repository ID:  $RepoId"
Write-Host "  PR ID:          $PrId"
Write-Host "  Copilot Model:  $CopilotModel"
Write-Host "  Max Files:      $MaxFiles"
Write-Host "  Debug:          $($Debug.IsPresent)"
Write-Host ""

# Change to task directory
$taskDir = Join-Path $PSScriptRoot "tasks\AICodeReviewTask"
Push-Location $taskDir

try {
    Write-Host "Running AI Code Review task..." -ForegroundColor Green
    Write-Host ""

    # Run the Node.js task
    node index.js

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Task completed successfully!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "Task failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    }
} finally {
    Pop-Location
}
