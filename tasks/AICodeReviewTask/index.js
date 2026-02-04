"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const tl = __importStar(require("azure-pipelines-task-lib/task"));
const path = __importStar(require("path"));
async function run() {
    try {
        // Get task inputs
        const githubPat = tl.getInput("githubPat", true);
        const adoPat = tl.getInput("adoPat", false) || "";
        const copilotModel = tl.getInput("copilotModel", false) || "";
        const maxFiles = tl.getInput("maxFiles", false) || "50";
        const maxLinesPerFile = tl.getInput("maxLinesPerFile", false) || "1000";
        const customPrompt = tl.getInput("customPrompt", false) || "";
        const promptFile = tl.getInput("promptFile", false) || "";
        const debug = tl.getInput("debug", false) || "false";
        const continueOnError = tl.getInput("continueOnError", false) || "true";
        // Get System.AccessToken
        const systemToken = tl.getVariable("System.AccessToken") || adoPat || "";
        if (!systemToken) {
            tl.setResult(tl.TaskResult.Failed, 'No Azure DevOps access token found. Enable "Allow scripts to access OAuth token" in pipeline settings, or provide an ADO PAT.');
            return;
        }
        // Resolve the Python script path
        const scriptPath = path.join(__dirname, "review_code.py");
        console.log(`Script path: ${scriptPath}`);
        // Find Python
        const pythonPath = tl.which("python3", false) || tl.which("python", true);
        console.log(`Python path: ${pythonPath}`);
        // Build the Python command
        const pythonRunner = tl.tool(pythonPath).arg(scriptPath);
        // Set environment variables for the Python script
        const envVars = {
            // Task inputs
            INPUT_GITHUB_PAT: githubPat,
            INPUT_ADO_PAT: adoPat,
            INPUT_COPILOT_MODEL: copilotModel,
            INPUT_MAX_FILES: maxFiles,
            INPUT_MAX_LINES_PER_FILE: maxLinesPerFile,
            INPUT_CUSTOM_PROMPT: customPrompt,
            INPUT_PROMPT_FILE: promptFile,
            INPUT_DEBUG: debug,
            INPUT_CONTINUE_ON_ERROR: continueOnError,
            // Azure DevOps system variables
            SYSTEM_ACCESSTOKEN: systemToken,
            // GitHub auth (for Copilot CLI)
            GH_TOKEN: githubPat,
            GITHUB_TOKEN: githubPat,
        };
        // Set env vars
        for (const [key, value] of Object.entries(envVars)) {
            if (value) {
                process.env[key] = value;
            }
        }
        // Execute the Python script
        const exitCode = await pythonRunner.exec({
            env: { ...process.env, ...envVars },
        });
        if (exitCode !== 0) {
            if (continueOnError === "true") {
                tl.setResult(tl.TaskResult.SucceededWithIssues, `Review script exited with code ${exitCode}`);
            }
            else {
                tl.setResult(tl.TaskResult.Failed, `Review script exited with code ${exitCode}`);
            }
        }
        else {
            tl.setResult(tl.TaskResult.Succeeded, "Code review completed");
        }
    }
    catch (err) {
        const continueOnError = tl.getInput("continueOnError", false) || "true";
        if (continueOnError === "true") {
            tl.setResult(tl.TaskResult.SucceededWithIssues, `Review failed: ${err.message}`);
        }
        else {
            tl.setResult(tl.TaskResult.Failed, `Review failed: ${err.message}`);
        }
    }
}
run();
