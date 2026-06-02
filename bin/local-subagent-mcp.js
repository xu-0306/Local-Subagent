#!/usr/bin/env node

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const packageRoot = path.resolve(__dirname, "..");
const packageJson = JSON.parse(
  fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"),
);
const cacheRoot = path.join(
  os.homedir(),
  ".local-subagent-mcp",
  packageJson.version,
);
const venvDir = path.join(cacheRoot, "venv");
const stampPath = path.join(cacheRoot, "install-stamp.json");

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    windowsHide: true,
    ...options,
  });

  if (result.error) {
    fail(`Failed to start ${command}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    process.exit(result.status === null ? 1 : result.status);
  }
}

function findPython() {
  const candidates = process.platform === "win32"
    ? [
        ["py", ["-3"]],
        ["python", []],
        ["python3", []],
      ]
    : [
        ["python3", []],
        ["python", []],
      ];

  for (const [command, prefixArgs] of candidates) {
    const probe = spawnSync(command, [...prefixArgs, "--version"], {
      stdio: "ignore",
      windowsHide: true,
    });
    if (!probe.error && probe.status === 0) {
      return { command, prefixArgs };
    }
  }
  fail(
    "Python 3.12+ is required to run local-subagent-mcp. Install Python, then run this MCP again.",
  );
}

function venvPythonPath() {
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
}

function readStamp() {
  if (!fs.existsSync(stampPath)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(stampPath, "utf8"));
  } catch {
    return null;
  }
}

function ensureInstalled() {
  const python = findPython();
  const targetStamp = {
    version: packageJson.version,
  };
  const currentStamp = readStamp();
  const pythonInVenv = venvPythonPath();

  if (currentStamp?.version === targetStamp.version && fs.existsSync(pythonInVenv)) {
    return pythonInVenv;
  }

  fs.mkdirSync(cacheRoot, { recursive: true });
  run(python.command, [...python.prefixArgs, "-m", "venv", venvDir]);
  run(pythonInVenv, ["-m", "pip", "install", "--upgrade", "pip"]);
  run(pythonInVenv, ["-m", "pip", "install", packageRoot]);
  fs.writeFileSync(stampPath, JSON.stringify(targetStamp, null, 2));
  return pythonInVenv;
}

function main() {
  const python = ensureInstalled();
  run(python, ["-m", "local_subagent", ...process.argv.slice(2)], {
    env: {
      ...process.env,
      PYTHONUTF8: "1",
    },
  });
}

main();
