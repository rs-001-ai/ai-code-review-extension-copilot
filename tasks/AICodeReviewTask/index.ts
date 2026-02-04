import * as tl from "azure-pipelines-task-lib/task";
import * as tr from "azure-pipelines-task-lib/toolrunner";
import * as path from "path";

async function run(): Promise<void> {
  try {
    // Get task inputs
    const githubPat: string = tl.getInput("githubPat", true)!;
    const adoPat: string = tl.getInput("adoPat", false) || "";
    const copilotModel: string = tl.getInput("copilotModel", false) || "";
    const maxFiles: string = tl.getInput("maxFiles", false) || "50";
    const maxLinesPerFile: string = tl.getInput("maxLinesPerFile", false) || "1000";
    const customPrompt: string = tl.getInput("customPrompt", false) || "";
    const promptFile: string = tl.getInput("promptFile", false) || "";
    const debug: string = tl.getInput("debug", false) || "false";
    const continueOnError: string = tl.getInput("continueOnError", false) || "true";

    // Get System.AccessToken
    const systemToken: string =
      tl.getVariable("System.AccessToken") || adoPat || "";

    if (!systemToken) {
      tl.setResult(
        tl.TaskResult.Failed,
        'No Azure DevOps access token found. Enable "Allow scripts to access OAuth token" in pipeline settings, or provide an ADO PAT.'
      );
      return;
    }

    // Resolve the Python script path
    const scriptPath: string = path.join(__dirname, "review_code.py");
    console.log(`Script path: ${scriptPath}`);

    // Find Python
    const pythonPath: string =
      tl.which("python3", false) || tl.which("python", true);
    console.log(`Python path: ${pythonPath}`);

    // Build the Python command
    const pythonRunner: tr.ToolRunner = tl.tool(pythonPath).arg(scriptPath);

    // Set environment variables for the Python script
    const envVars: { [key: string]: string } = {
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
    const exitCode: number = await pythonRunner.exec({
      env: { ...process.env, ...envVars },
    } as tr.IExecOptions);

    if (exitCode !== 0) {
      if (continueOnError === "true") {
        tl.setResult(
          tl.TaskResult.SucceededWithIssues,
          `Review script exited with code ${exitCode}`
        );
      } else {
        tl.setResult(
          tl.TaskResult.Failed,
          `Review script exited with code ${exitCode}`
        );
      }
    } else {
      tl.setResult(tl.TaskResult.Succeeded, "Code review completed");
    }
  } catch (err: any) {
    const continueOnError: string =
      tl.getInput("continueOnError", false) || "true";

    if (continueOnError === "true") {
      tl.setResult(
        tl.TaskResult.SucceededWithIssues,
        `Review failed: ${err.message}`
      );
    } else {
      tl.setResult(tl.TaskResult.Failed, `Review failed: ${err.message}`);
    }
  }
}

run();
