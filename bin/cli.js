#!/usr/bin/env node

/**
 * Release Announcement Video Skill CLI
 * Allows installing the skill into any code editor / AI agent (Antigravity, Cursor, Claude Code, Windsurf, Copilot, etc.)
 * or generating release announcement videos with 1 command.
 */

const fs = require('fs');
const path = require('path');
const { spawn, execSync } = require('child_process');

const SKILL_NAME = 'release-announcement-video';
const PKG_ROOT = path.resolve(__dirname, '..');

// Terminal colors
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  magenta: '\x1b[35m',
  blue: '\x1b[34m',
};

function log(msg = '') {
  console.log(msg);
}

function logInfo(msg) {
  console.log(`${colors.cyan}ℹ${colors.reset} ${msg}`);
}

function logSuccess(msg) {
  console.log(`${colors.green}✔${colors.reset} ${msg}`);
}

function logWarn(msg) {
  console.log(`${colors.yellow}⚠${colors.reset} ${msg}`);
}

function logError(msg) {
  console.error(`${colors.red}✖${colors.reset} ${msg}`);
}

// Copy directory recursively
function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

// Editor / Agent target configurations
function getAgentTargets(targetDir = process.cwd(), isGlobal = false) {
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  
  if (isGlobal) {
    return [
      {
        id: 'antigravity-global',
        name: 'Antigravity / Gemini (Global Config)',
        dest: path.join(homeDir, '.gemini', 'config', 'skills', SKILL_NAME),
      },
      {
        id: 'claude-global',
        name: 'Claude Code (Global Config)',
        dest: path.join(homeDir, '.claude', 'skills', SKILL_NAME),
      },
      {
        id: 'agents-global',
        name: 'Universal Agents (Global Config)',
        dest: path.join(homeDir, '.agents', 'skills', SKILL_NAME),
      },
    ];
  }

  return [
    {
      id: 'antigravity',
      name: 'Antigravity / Google AI (.agents/skills)',
      dest: path.join(targetDir, '.agents', 'skills', SKILL_NAME),
      detected: fs.existsSync(path.join(targetDir, '.agents')),
    },
    {
      id: 'cursor',
      name: 'Cursor IDE (.cursor/skills)',
      dest: path.join(targetDir, '.cursor', 'skills', SKILL_NAME),
      detected: fs.existsSync(path.join(targetDir, '.cursor')) || fs.existsSync(path.join(targetDir, '.cursorrules')),
    },
    {
      id: 'claude',
      name: 'Claude Code (.claude/skills)',
      dest: path.join(targetDir, '.claude', 'skills', SKILL_NAME),
      detected: fs.existsSync(path.join(targetDir, '.claude')) || fs.existsSync(path.join(targetDir, 'CLAUDE.md')),
    },
    {
      id: 'windsurf',
      name: 'Windsurf / Cascade (.windsurf/skills)',
      dest: path.join(targetDir, '.windsurf', 'skills', SKILL_NAME),
      detected: fs.existsSync(path.join(targetDir, '.windsurf')) || fs.existsSync(path.join(targetDir, '.windsurfrules')),
    },
    {
      id: 'copilot',
      name: 'GitHub Copilot / VS Code (.agents/skills)',
      dest: path.join(targetDir, '.agents', 'skills', SKILL_NAME),
      detected: fs.existsSync(path.join(targetDir, '.github')),
    },
    {
      id: 'cline',
      name: 'Cline / Roo Code (.agents/skills)',
      dest: path.join(targetDir, '.agents', 'skills', SKILL_NAME),
      detected: fs.existsSync(path.join(targetDir, '.clinerules')),
    },
  ];
}

// Check system dependencies
function checkPrerequisites() {
  const status = {
    python: false,
    playwright: false,
    ffmpeg: false,
  };

  try {
    const py = process.platform === 'win32' ? 'python' : 'python3';
    execSync(`${py} --version`, { stdio: 'ignore' });
    status.python = true;
  } catch (e) {}

  try {
    const py = process.platform === 'win32' ? 'python' : 'python3';
    execSync(`${py} -c "import playwright"`, { stdio: 'ignore' });
    status.playwright = true;
  } catch (e) {}

  try {
    execSync('ffmpeg -version', { stdio: 'ignore' });
    status.ffmpeg = true;
  } catch (e) {}

  return status;
}

// Command: Doctor / Check
function handleDoctor() {
  log(`\n${colors.bright}${colors.cyan}🎬 Release Announcement Video - Environment Health Check${colors.reset}\n`);
  const status = checkPrerequisites();

  log(`Python 3.10+ : ${status.python ? colors.green + '✔ Installed' : colors.red + '✖ Not Found'}${colors.reset}`);
  log(`Playwright   : ${status.playwright ? colors.green + '✔ Installed' : colors.yellow + '⚠ Missing (pip install playwright && playwright install chromium)'}${colors.reset}`);
  log(`FFmpeg       : ${status.ffmpeg ? colors.green + '✔ Installed' : colors.yellow + '⚠ Missing (Ensure ffmpeg is on system PATH)'}${colors.reset}`);

  if (status.python && status.playwright && status.ffmpeg) {
    log(`\n${colors.green}${colors.bright}🎉 All dependencies are ready!${colors.reset}\n`);
  } else {
    log(`\n${colors.yellow}To install missing dependencies:${colors.reset}`);
    if (!status.playwright) {
      log(`  ${colors.dim}$${colors.reset} pip install playwright && playwright install chromium`);
    }
    if (!status.ffmpeg) {
      log(`  ${colors.dim}Windows:${colors.reset} winget install Gyan.FFmpeg (or choco install ffmpeg)`);
      log(`  ${colors.dim}macOS:  ${colors.reset} brew install ffmpeg`);
      log(`  ${colors.dim}Linux:  ${colors.reset} sudo apt install ffmpeg`);
    }
    log();
  }
}

// Copy skill contents to target directory
function installSkillToPath(targetDir) {
  const skillFiles = ['SKILL.md', 'README.md', 'LICENSE'];
  const skillDirs = ['scripts', 'references', 'examples'];

  fs.mkdirSync(targetDir, { recursive: true });

  for (const file of skillFiles) {
    const src = path.join(PKG_ROOT, file);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, path.join(targetDir, file));
    }
  }

  for (const dir of skillDirs) {
    const src = path.join(PKG_ROOT, dir);
    if (fs.existsSync(src)) {
      copyDirSync(src, path.join(targetDir, dir));
    }
  }
}

// Command: Add / Install Skill
function handleAdd(args) {
  const isGlobal = args.includes('--global') || args.includes('-g');
  const agentArgIdx = args.findIndex((a) => a === '--agent' || a === '-a');
  const specifiedAgent = agentArgIdx !== -1 ? args[agentArgIdx + 1]?.toLowerCase() : null;
  const isAll = args.includes('--all');

  log(`\n${colors.bright}${colors.cyan}🎬 Release Announcement Video - Skill Installer${colors.reset}\n`);

  const targets = getAgentTargets(process.cwd(), isGlobal);
  let targetsToInstall = [];

  if (isGlobal) {
    targetsToInstall = targets;
  } else if (isAll) {
    targetsToInstall = targets;
  } else if (specifiedAgent) {
    const match = targets.filter(
      (t) => t.id === specifiedAgent || t.id.includes(specifiedAgent) || specifiedAgent === 'all'
    );
    if (match.length > 0) {
      targetsToInstall = match;
    } else {
      logWarn(`Unknown agent '${specifiedAgent}'. Installing to standard '.agents/skills/' directory.`);
      targetsToInstall = [targets[0]];
    }
  } else {
    // Auto-detect or default to standard .agents / detected editors
    const detected = targets.filter((t) => t.detected);
    if (detected.length > 0) {
      targetsToInstall = detected;
      logInfo(`Detected active AI tools in workspace: ${detected.map((d) => colors.magenta + d.name + colors.reset).join(', ')}`);
    } else {
      // Default to standard universal agents directory
      targetsToInstall = [targets[0]]; // .agents/skills
    }
  }

  for (const target of targetsToInstall) {
    installSkillToPath(target.dest);
    logSuccess(`Installed skill into ${colors.bright}${target.name}${colors.reset}\n   Path: ${colors.dim}${target.dest}${colors.reset}`);
  }

  log(`\n${colors.green}${colors.bright}✅ Skill successfully added!${colors.reset}`);
  log(`\n${colors.bright}How to use with your AI Agent:${colors.reset}`);
  log(`  ${colors.cyan}Prompt:${colors.reset} "Make a release video for our latest release on http://localhost:3000"`);
  log(`  ${colors.cyan}Quick CLI:${colors.reset} npx release-announcement-video generate --url http://localhost:3000\n`);
}

// Command: Generate Video
function handleGenerate(args) {
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const autoScript = path.join(PKG_ROOT, 'scripts', 'auto_release.py');

  const childArgs = [autoScript, ...args];
  const child = spawn(py, childArgs, { stdio: 'inherit', cwd: process.cwd() });

  child.on('close', (code) => {
    process.exit(code || 0);
  });
}

// Help text
function showHelp() {
  log(`
${colors.bright}${colors.cyan}🎬 Release Announcement Video Skill${colors.reset}
Turn software releases into ready-to-post announcement videos & social copy for any AI agent or code editor.

${colors.bright}USAGE:${colors.reset}
  ${colors.cyan}npx release-announcement-video${colors.reset} [command] [options]

${colors.bright}COMMANDS:${colors.reset}
  ${colors.green}add, init, install${colors.reset}    Add the skill into your project or code editor
  ${colors.green}generate, run, create${colors.reset} Generate a release video and announcement copy in 1 command
  ${colors.green}doctor, check${colors.reset}         Verify Python, Playwright, and FFmpeg environment
  ${colors.green}help, --help${colors.reset}          Show this help message

${colors.bright}OPTIONS for 'add':${colors.reset}
  ${colors.yellow}--agent <name>${colors.reset}       Target specific editor/agent:
                         ${colors.dim}antigravity, cursor, claude, windsurf, copilot, cline, all${colors.reset}
  ${colors.yellow}--global, -g${colors.reset}         Install into global AI agent skills directory
  ${colors.yellow}--all${colors.reset}                Install into all supported agent configurations

${colors.bright}OPTIONS for 'generate':${colors.reset}
  ${colors.yellow}--url <url>${colors.reset}          Base URL where the live app is running (e.g. http://localhost:3000)
  ${colors.yellow}--repo <path>${colors.reset}        Path to repository (default: current directory)
  ${colors.yellow}--from <tag/commit>${colors.reset}  Starting git ref or previous release tag
  ${colors.yellow}--to <tag/commit>${colors.reset}    Target git ref or current release tag (default: HEAD)
  ${colors.yellow}--format <fmt>${colors.reset}       ${colors.dim}landscape${colors.reset} (default), ${colors.dim}vertical${colors.reset}, or ${colors.dim}square${colors.reset}
  ${colors.yellow}--dry-run${colors.reset}            Check selectors and the denylist, do not record
  ${colors.yellow}--before-after${colors.reset}      Before card from the previous tag (no checkout)
  ${colors.yellow}--before-url <url>${colors.reset}  Film an already-running old build
  ${colors.yellow}--device-frame <f>${colors.reset}  Wrap features in a device template: ${colors.dim}macos, browser, glass, iphone, laptop, ipad${colors.reset}
  ${colors.yellow}--frame-background${colors.reset}  Background preset, hex, or image path (default: gradient-sky)
  ${colors.yellow}--output <path>${colors.reset}      Output MP4 file path

${colors.bright}EXAMPLES:${colors.reset}
  ${colors.dim}# 1. Add skill to Cursor, Claude, Antigravity, or Windsurf:${colors.reset}
  $ npx release-announcement-video add
  $ npx release-announcement-video add --agent cursor
  $ npx release-announcement-video add --global

  ${colors.dim}# 2. Generate a release video in 1 step:${colors.reset}
  $ npx release-announcement-video generate --url http://localhost:3000
  $ npx release-announcement-video generate --url https://staging.myapp.com --format vertical
`);
}

// Main CLI router
function main() {
  const rawArgs = process.argv.slice(2);
  const command = rawArgs[0] || 'add';
  const restArgs = rawArgs.slice(1);

  if (rawArgs.includes('--help') || rawArgs.includes('-h') || command === 'help') {
    showHelp();
    return;
  }

  switch (command.toLowerCase()) {
    case 'add':
    case 'init':
    case 'install':
      handleAdd(restArgs);
      break;
    case 'doctor':
    case 'check':
      handleDoctor();
      break;
    case 'generate':
    case 'run':
    case 'create':
      handleGenerate(restArgs);
      break;
    default:
      if (command.startsWith('--')) {
        // e.g. npx release-announcement-video --agent cursor
        handleAdd(rawArgs);
      } else {
        showHelp();
      }
      break;
  }
}

main();
