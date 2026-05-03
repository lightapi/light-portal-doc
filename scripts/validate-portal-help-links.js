#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const REQUIRED_OWNER_SCOPED_PAGE_ROUTES = [
  "/app/service/admin",
  "/app/apiDetail",
  "/app/clientApp",
  "/app/oauth/authClient",
  "/app/oauth/clientToken",
  "/app/instance/InstanceAdmin",
  "/app/instance/RuntimeInstanceAdmin",
  "/app/instance/InstanceApi",
  "/app/instance/InstanceApiPathPrefix",
  "/app/instance/InstanceApp",
  "/app/instance/InstanceAppApi",
  "/app/schedule/admin",
  "/app/workflow/WfDefinition",
];

const REQUIRED_HIGH_VALUE_FORM_IDS = [
  "createApi",
  "updateApi",
  "createApiVersion",
  "updateApiVersion",
  "createApp",
  "updateApp",
  "createClient",
  "updateClient",
  "createClientToken",
  "createInstance",
  "updateInstance",
  "createInstanceApi",
  "createInstanceApiPathPrefix",
  "updateInstanceApiPathPrefix",
  "createInstanceApp",
  "createInstanceAppApi",
  "createRuntimeInstance",
  "updateRuntimeInstance",
  "createSchedule",
  "updateSchedule",
  "createWfDefinition",
  "updateWfDefinition",
];

function usage() {
  return [
    "Usage: node scripts/validate-portal-help-links.js [--portal-view DIR] [--docs-root DIR]",
    "",
    "Defaults:",
    "  --docs-root    current working directory",
    "  --portal-view  PORTAL_VIEW_DIR env var, or ../portal-view from docs root",
  ].join("\n");
}

function parseArgs(argv) {
  const args = {};

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") {
      console.log(usage());
      process.exit(0);
    }

    if (arg === "--portal-view") {
      args.portalViewDir = argv[i + 1];
      i += 1;
      continue;
    }

    if (arg === "--docs-root") {
      args.docsRoot = argv[i + 1];
      i += 1;
      continue;
    }

    throw new Error(`Unknown argument: ${arg}\n${usage()}`);
  }

  return args;
}

function readText(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function requireFile(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${label} does not exist: ${filePath}`);
  }
}

function helpSourceLabel(filePath, name) {
  return `${path.relative(process.cwd(), filePath)}${name ? `:${name}` : ""}`;
}

function addHelpPath(helpPaths, helpPath, source) {
  if (!helpPath) return;
  if (!helpPaths.has(helpPath)) helpPaths.set(helpPath, []);
  helpPaths.get(helpPath).push(source);
}

function extractHelpPathsFromText(helpPaths, filePath) {
  const text = readText(filePath);
  const regex = /helpPath:\s*["'`]([^"'`]+)["'`]/g;
  let match;

  while ((match = regex.exec(text)) !== null) {
    addHelpPath(helpPaths, match[1], helpSourceLabel(filePath, `line ${lineNumber(text, match.index)}`));
  }
}

function lineNumber(text, index) {
  return text.slice(0, index).split("\n").length;
}

function parseForms(formsPath) {
  return JSON.parse(readText(formsPath));
}

function extractFormHelpPaths(helpPaths, formsPath, forms) {
  for (const [formId, form] of Object.entries(forms)) {
    if (form && typeof form === "object") {
      addHelpPath(helpPaths, form.helpPath, helpSourceLabel(formsPath, formId));
    }
  }
}

function extractPageRegistryEntries(pageRegistryPath) {
  const text = readText(pageRegistryPath);
  const entries = [];
  const pageEntryRegex = /\{\s*id:\s*"([^"]+)"[\s\S]*?route:\s*"([^"]+)"[\s\S]*?\},/g;
  let match;

  while ((match = pageEntryRegex.exec(text)) !== null) {
    const block = match[0];
    const helpPathMatch = block.match(/helpPath:\s*["'`]([^"'`]+)["'`]/);

    entries.push({
      id: match[1],
      route: match[2],
      helpPath: helpPathMatch?.[1],
    });
  }

  return entries;
}

function markdownPathForHelpPath(docsSrcDir, helpPath) {
  return path.join(docsSrcDir, `${helpPath.replace(/^\/+/, "")}.md`);
}

function isStableHelpPath(helpPath) {
  if (helpPath === "/help/portal-view/index") return true;

  return /^\/help\/portal-view\/(?:pages|forms|tasks|concepts)\/[a-z0-9]+(?:-[a-z0-9]+)*$/.test(helpPath);
}

function relativeDisplay(filePath) {
  return path.relative(process.cwd(), filePath);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const docsRoot = path.resolve(args.docsRoot ?? process.cwd());
  const portalViewDir = path.resolve(
    args.portalViewDir
      ?? process.env.PORTAL_VIEW_DIR
      ?? path.join(docsRoot, "..", "portal-view"),
  );
  const docsSrcDir = path.join(docsRoot, "src");
  const pageRegistryPath = path.join(portalViewDir, "src", "tasks", "pageRegistry.ts");
  const taskRegistryPath = path.join(portalViewDir, "src", "tasks", "taskRegistry.ts");
  const formsPath = path.join(portalViewDir, "src", "data", "Forms.json");

  requireFile(docsSrcDir, "Docs src directory");
  requireFile(pageRegistryPath, "portal-view page registry");
  requireFile(taskRegistryPath, "portal-view task registry");
  requireFile(formsPath, "portal-view Forms.json");

  const helpPaths = new Map();
  const forms = parseForms(formsPath);
  const pageEntries = extractPageRegistryEntries(pageRegistryPath);

  extractHelpPathsFromText(helpPaths, pageRegistryPath);
  extractHelpPathsFromText(helpPaths, taskRegistryPath);
  extractFormHelpPaths(helpPaths, formsPath, forms);

  const errors = [];
  const warnings = [];

  for (const [helpPath, sources] of helpPaths.entries()) {
    if (!isStableHelpPath(helpPath)) {
      errors.push([
        `Unstable helpPath: ${helpPath}`,
        `  Sources: ${sources.join(", ")}`,
        "  Expected: /help/portal-view/{pages|forms|tasks|concepts}/lowercase-slug",
      ].join("\n"));
      continue;
    }

    const markdownPath = markdownPathForHelpPath(docsSrcDir, helpPath);
    if (!fs.existsSync(markdownPath)) {
      errors.push([
        `Missing help markdown for ${helpPath}`,
        `  Expected: ${relativeDisplay(markdownPath)}`,
        `  Sources: ${sources.join(", ")}`,
      ].join("\n"));
    }
  }

  for (const route of REQUIRED_OWNER_SCOPED_PAGE_ROUTES) {
    const page = pageEntries.find((entry) => entry.route === route);
    if (!page) {
      errors.push(`Required owner-scoped page route is missing from pageRegistry.ts: ${route}`);
      continue;
    }

    if (!page.helpPath) {
      errors.push(`Required owner-scoped page is missing helpPath: ${page.id} (${route})`);
      continue;
    }

    if (!fs.existsSync(markdownPathForHelpPath(docsSrcDir, page.helpPath))) {
      errors.push(`Required owner-scoped page help doc is missing: ${page.id} -> ${page.helpPath}`);
    }
  }

  for (const formId of REQUIRED_HIGH_VALUE_FORM_IDS) {
    const form = forms[formId];
    if (!form) {
      errors.push(`Required high-value form is missing from Forms.json: ${formId}`);
      continue;
    }

    if (!form.helpPath) {
      errors.push(`Required high-value form is missing helpPath: ${formId}`);
      continue;
    }

    if (!fs.existsSync(markdownPathForHelpPath(docsSrcDir, form.helpPath))) {
      errors.push(`Required high-value form help doc is missing: ${formId} -> ${form.helpPath}`);
    }
  }

  const docsHelpRoot = path.join(docsSrcDir, "help", "portal-view");
  if (!fs.existsSync(docsHelpRoot)) {
    errors.push(`Portal help root is missing: ${relativeDisplay(docsHelpRoot)}`);
  }

  const summaryPath = path.join(docsSrcDir, "SUMMARY.md");
  if (fs.existsSync(summaryPath)) {
    const summary = readText(summaryPath);
    for (const helpPath of helpPaths.keys()) {
      const relativeDocPath = `.${helpPath}.md`;
      if (!summary.includes(relativeDocPath)) {
        warnings.push(`Configured helpPath is not listed in SUMMARY.md: ${helpPath}`);
      }
    }
  }

  if (warnings.length > 0) {
    console.warn("Portal help validation warnings:");
    for (const warning of warnings) console.warn(`- ${warning}`);
  }

  if (errors.length > 0) {
    console.error("Portal help validation failed:");
    for (const error of errors) console.error(`\n${error}`);
    process.exit(1);
  }

  console.log("Portal help validation passed.");
  console.log(`- Configured help paths: ${helpPaths.size}`);
  console.log(`- Required owner-scoped pages: ${REQUIRED_OWNER_SCOPED_PAGE_ROUTES.length}`);
  console.log(`- Required high-value forms: ${REQUIRED_HIGH_VALUE_FORM_IDS.length}`);
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
}
