#!/bin/bash
# Local Test Script for AI Code Review Extension
# Usage: ./test-local.sh --github-pat "your-pat" --ado-org "org" --ado-project "project" --repo-id "repo" --pr-id "123"

set -e

# Default values
COPILOT_MODEL="claude-sonnet-4.5"
MAX_FILES="50"
MAX_LINES_PER_FILE="1000"
DEBUG="false"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --github-pat) GITHUB_PAT="$2"; shift 2 ;;
        --ado-pat) ADO_PAT="$2"; shift 2 ;;
        --ado-org) ADO_ORG="$2"; shift 2 ;;
        --ado-project) ADO_PROJECT="$2"; shift 2 ;;
        --repo-id) REPO_ID="$2"; shift 2 ;;
        --pr-id) PR_ID="$2"; shift 2 ;;
        --model) COPILOT_MODEL="$2"; shift 2 ;;
        --max-files) MAX_FILES="$2"; shift 2 ;;
        --debug) DEBUG="true"; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Validate required arguments
if [[ -z "$GITHUB_PAT" || -z "$ADO_ORG" || -z "$ADO_PROJECT" || -z "$REPO_ID" || -z "$PR_ID" ]]; then
    echo "Usage: ./test-local.sh --github-pat PAT --ado-org ORG --ado-project PROJECT --repo-id REPO --pr-id PR"
    echo ""
    echo "Required:"
    echo "  --github-pat    GitHub PAT with Copilot access"
    echo "  --ado-org       Azure DevOps organization name"
    echo "  --ado-project   Azure DevOps project name"
    echo "  --repo-id       Repository ID (GUID)"
    echo "  --pr-id         Pull Request ID"
    echo ""
    echo "Optional:"
    echo "  --ado-pat       Azure DevOps PAT (defaults to GitHub PAT)"
    echo "  --model         Copilot model (default: claude-sonnet-4.5)"
    echo "  --max-files     Max files to review (default: 50)"
    echo "  --debug         Enable debug logging"
    exit 1
fi

# Use GitHub PAT for ADO if not specified
ADO_PAT=${ADO_PAT:-$GITHUB_PAT}

echo "================================"
echo "AI Code Review - Local Test"
echo "================================"
echo ""
echo "Configuration:"
echo "  ADO Org:        $ADO_ORG"
echo "  ADO Project:    $ADO_PROJECT"
echo "  Repository ID:  $REPO_ID"
echo "  PR ID:          $PR_ID"
echo "  Copilot Model:  $COPILOT_MODEL"
echo "  Debug:          $DEBUG"
echo ""

# Set environment variables
export INPUT_GITHUBPAT="$GITHUB_PAT"
export INPUT_ADOPAT="$ADO_PAT"
export INPUT_COPILOTMODEL="$COPILOT_MODEL"
export INPUT_MAXFILES="$MAX_FILES"
export INPUT_MAXLINESPERFILE="$MAX_LINES_PER_FILE"
export INPUT_DEBUG="$DEBUG"
export INPUT_CONTINUEONERROR="true"

export SYSTEM_TEAMFOUNDATIONCOLLECTIONURI="https://dev.azure.com/$ADO_ORG/"
export SYSTEM_TEAMPROJECTID="$ADO_PROJECT"
export BUILD_REPOSITORY_ID="$REPO_ID"
export SYSTEM_PULLREQUEST_PULLREQUESTID="$PR_ID"
export SYSTEM_ACCESSTOKEN="$ADO_PAT"

export GH_TOKEN="$GITHUB_PAT"
export GITHUB_TOKEN="$GITHUB_PAT"

# Change to task directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/tasks/AICodeReviewTask"

echo "Running AI Code Review task..."
echo ""

node index.js

echo ""
echo "Task completed!"
