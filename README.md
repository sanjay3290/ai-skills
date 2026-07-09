# AI Agent Skills

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sanjay3290/ai-skills)

A collection of portable skills for AI coding assistants. Works with all major AI clients that support the [Agent Skills Standard](https://agentskills.io).

## Supported AI Clients

<p align="center">
  <a href="#claude-code"><img src="https://img.shields.io/badge/Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude Code" /></a>
  <a href="#gemini-cli"><img src="https://img.shields.io/badge/Gemini_CLI-8E75B2?style=for-the-badge&logo=google&logoColor=white" alt="Gemini CLI" /></a>
  <a href="#google-antigravity"><img src="https://img.shields.io/badge/Antigravity-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google Antigravity" /></a>
  <a href="#cursor"><img src="https://img.shields.io/badge/Cursor-000000?style=for-the-badge&logo=cursor&logoColor=white" alt="Cursor" /></a>
  <a href="#openai-codex-cli"><img src="https://img.shields.io/badge/OpenAI_Codex-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI Codex" /></a>
  <a href="#goose"><img src="https://img.shields.io/badge/Goose-FF6B35?style=for-the-badge&logo=go&logoColor=white" alt="Goose" /></a>
</p>

| Client | Skills Directory | Documentation |
|--------|-----------------|---------------|
| **Claude Code** | `~/.claude/skills/` or `.claude/skills/` | [docs](https://docs.anthropic.com/en/docs/claude-code/skills) |
| **Gemini CLI** | `~/.gemini/skills/` or `.gemini/skills/` | [docs](https://geminicli.com/docs/cli/skills/) |
| **Google Antigravity** | `~/.gemini/antigravity/skills/` or `.agent/skills/` | [docs](https://antigravity.google/docs/skills) |
| **Cursor** | `~/.cursor/skills/` or `.cursor/skills/` | [docs](https://cursor.com/docs/context/skills) |
| **OpenAI Codex CLI** | `~/.codex/skills/` or `.codex/skills/` | [docs](https://developers.openai.com/codex/skills/) |
| **Goose** | `~/.config/goose/skills/` or `.goose/skills/` | [docs](https://block.github.io/goose/docs/guides/context-engineering/using-skills/) |

## Available Skills

| Skill | Description |
|-------|-------------|
| [postgres](skills/postgres/) | Read-only PostgreSQL queries with defense-in-depth security |
| [mysql](skills/mysql/) | Read-only MySQL queries with session-level write protection |
| [mssql](skills/mssql/) | Read-only Microsoft SQL Server queries with query validation security |
| [imagen](skills/imagen/) | AI image generation using Google Gemini (cross-platform) |
| [deep-research](skills/deep-research/) | Autonomous multi-step research using Gemini Deep Research Agent |
| [outline](skills/outline/) | Search, read, and manage Outline wiki documents |
| [jules](skills/jules/) | Delegate coding tasks to Google Jules AI agent (async bug fixes, docs, tests, features) |
| [manus](skills/manus/) | Delegate complex tasks to Manus AI agent (deep research, market analysis, reports) |
| [grok-build](skills/grok-build/) | Orchestrate coding by delegating well-specified tasks to xAI's Grok Build CLI headlessly — the assistant plans, specs, dispatches, and reviews every diff |
| [notebooklm](skills/notebooklm/) | Query and manage Google NotebookLM notebooks with persistent profile auth, source sync, batch/multi queries, and structured exports |
| [elevenlabs](skills/elevenlabs/) | Text-to-speech narration and two-host podcast generation from documents (PDF, DOCX, MD, TXT) using ElevenLabs API |
| [google-tts](skills/google-tts/) | Text-to-speech narration and podcast generation using Google Cloud TTS (Neural2, WaveNet, Studio voices, 40+ languages) |
| [atlassian](skills/atlassian/) | Manage Jira issues and Confluence wiki pages in Atlassian Cloud (OAuth 2.1 via MCP server or API token fallback) |
| [azure-devops](skills/azure-devops/) | Manage Azure DevOps projects, work items, repos, PRs, pipelines, wikis, test plans, security alerts, variable groups, environments/approvals, branch policies, and attachments (99 tools, 13 domains) |
| [apple-container](skills/apple-container/) | Build, run, and manage OCI/Linux containers as lightweight VMs on Apple-silicon macOS with Apple's `container` CLI — no Docker daemon |
| [telegram](skills/telegram/) | Send Telegram messages, files, and alerts via bot; ask-and-wait approvals with inline buttons; multi-bot and multi-target routing; Claude Code hook integration |

### Google Workspace Skills

Lightweight alternatives to the full [Google Workspace MCP server](https://github.com/gemini-cli-extensions/workspace). Each skill has standalone OAuth authentication with cross-platform token storage via keyring.

> **⚠️ Requires Google Workspace account.** Personal Gmail accounts are not supported. These skills use the same OAuth infrastructure as the official Google Workspace MCP.

| Skill | Description |
|-------|-------------|
| [google-chat](skills/google-chat/) | List spaces, send messages, DMs, create spaces |
| [google-docs](skills/google-docs/) | Create, read, edit Google Docs |
| [google-sheets](skills/google-sheets/) | Read spreadsheets, get ranges, find sheets |
| [google-slides](skills/google-slides/) | Read presentations, get text and metadata |
| [google-drive](skills/google-drive/) | Search files, list folders, download files |
| [google-calendar](skills/google-calendar/) | Events, scheduling, free time lookup |
| [gmail](skills/gmail/) | Search, read, send emails, manage labels |

## Installation

> **[`npx skills`](https://github.com/vercel-labs/skills)** — The package manager for the open [Agent Skills](https://agentskills.io) ecosystem. One command to install skills into any AI coding agent.

### Install Skills

```bash
# Browse all 22 available skills
npx skills add sanjay3290/ai-skills --list

# Install a single skill (auto-detects your agent)
npx skills add sanjay3290/ai-skills --skill postgres

# Install multiple skills at once
npx skills add sanjay3290/ai-skills --skill postgres --skill mysql --skill mssql

# Install all skills
npx skills add sanjay3290/ai-skills --all
```

### Target Specific Agents

Use `-a` to install into a specific agent's skills directory:

```bash
# Install for Claude Code
npx skills add sanjay3290/ai-skills --skill postgres -a claude-code

# Install for multiple agents at once
npx skills add sanjay3290/ai-skills --skill postgres -a claude-code -a gemini-cli -a cursor

# Install all skills into all supported agents
npx skills add sanjay3290/ai-skills --all -a '*'
```

### Global vs Project Install

By default, skills install to the current project directory. Use `-g` for global (user-level) installation:

```bash
# Global install — available in all projects
npx skills add sanjay3290/ai-skills --skill imagen -g

# Project install (default) — scoped to current repo
npx skills add sanjay3290/ai-skills --skill imagen
```

### Supported Agents

The skills CLI supports 40+ agents. Here are the most common:

| Agent | `-a` Flag | Project Directory | Global Directory |
|-------|-----------|-------------------|------------------|
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| Gemini CLI | `gemini-cli` | `.gemini/skills/` | `~/.gemini/skills/` |
| Cursor | `cursor` | `.cursor/skills/` | `~/.cursor/skills/` |
| OpenAI Codex | `codex` | `.codex/skills/` | `~/.codex/skills/` |
| Goose | `goose` | `.goose/skills/` | `~/.config/goose/skills/` |
| GitHub Copilot | `github-copilot` | `.github/skills/` | `~/.github/skills/` |
| Google Antigravity | `antigravity` | `.agent/skills/` | `~/.gemini/antigravity/skills/` |
| All agents | `'*'` | auto-detected | auto-detected |

### Managing Skills

```bash
# List installed skills
npx skills list

# Check for updates
npx skills check

# Update all skills
npx skills update

# Remove a specific skill
npx skills remove postgres

# Remove all skills from a specific agent
npx skills remove --skill '*' -a cursor
```

### Discover More Skills

```bash
# Search the skills.sh directory
npx skills find postgres

# Browse all community skills
npx skills find
```

Visit [skills.sh](https://skills.sh) for the full directory of community skills.

<details>
<summary><b>Manual Installation (Alternative)</b></summary>

#### Clone entire repository

```bash
git clone https://github.com/sanjay3290/ai-skills.git ~/.claude/skills/ai-skills
```

#### Copy individual skills

```bash
cp -r skills/postgres ~/.claude/skills/
```

#### Symlink for development

```bash
ln -s /path/to/ai-skills/skills/postgres ~/.claude/skills/postgres
```

Replace `~/.claude/skills/` with the appropriate directory for your agent (see table above).

</details>

## Skill Setup

Each skill may require additional configuration:

### Postgres / MySQL / MSSQL
Create `connections.json` in the skill directory with your database credentials. See [postgres/README.md](skills/postgres/README.md), [mysql/README.md](skills/mysql/README.md), or [mssql/README.md](skills/mssql/README.md).

```bash
# Install drivers for whichever databases you use
pip install psycopg2-binary     # PostgreSQL
pip install mysql-connector-python  # MySQL
pip install pymssql              # MSSQL
```

### Imagen & Deep Research
```bash
export GEMINI_API_KEY=your-api-key
```
Get a free key at [Google AI Studio](https://aistudio.google.com/).

> **Note:** Deep Research tasks take 2-10 minutes and cost $2-5 per query.

### Outline
```bash
export OUTLINE_API_KEY=your-api-key
export OUTLINE_API_URL=https://your-wiki.example.com/api  # Optional
```
Get your API key from your Outline wiki settings.

### Jules
```bash
# Install CLI (one-time)
npm install -g @google/jules

# Authenticate (opens browser)
jules login
```
Connect your GitHub repos at [jules.google.com](https://jules.google.com). Jules works asynchronously - create a task, it runs in the background, then pull results when complete.

### Manus
```bash
export MANUS_API_KEY=your-api-key
```
Get your API key from [manus.im](https://manus.im) settings. Manus excels at deep research, market analysis, product comparisons, and generating comprehensive reports with visualizations.

### Grok Build
Install xAI's Grok CLI per their docs, then authenticate:
```bash
grok login
```
Verify with `grok models`. The skill runs `grok` headlessly (`--always-approve`) and reviews every diff before committing. Works on macOS, Linux, and Windows (PowerShell).

### ElevenLabs
```bash
pip install -r skills/elevenlabs/requirements.txt  # Only needed for PDF/DOCX
```
Create `skills/elevenlabs/config.json` (see `config.example.json`) or set `ELEVENLABS_API_KEY` env var. Requires `ffmpeg` for multi-chunk narration and podcasts.

Get your API key at [elevenlabs.io](https://elevenlabs.io/).

### Google TTS
```bash
export GOOGLE_TTS_API_KEY=your-api-key
pip install PyPDF2 python-docx  # Only needed for PDF/DOCX files
```
Enable the [Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com) and create an API key in your GCP project. Requires `ffmpeg` for multi-chunk documents and podcasts.

### NotebookLM
```bash
pip install -r skills/notebooklm/requirements.txt
python -m playwright install chromium
```
Use `python skills/notebooklm/scripts/auth_manager.py setup` for one-time login.

### Atlassian (Jira + Confluence)
```bash
pip install -r skills/atlassian/requirements.txt

# Option A: OAuth via MCP Server (Recommended)
python skills/atlassian/scripts/auth.py login --oauth

# Option B: API Token
python skills/atlassian/scripts/auth.py login
```

### Azure DevOps
```bash
pip install keyring

# Option A: OAuth (Recommended)
python skills/azure-devops/scripts/auth.py login --org MyOrganization

# Option B: PAT
python skills/azure-devops/scripts/auth.py login --org MyOrganization --pat YOUR_PAT
```

### Google Workspace Skills
Each Google Workspace skill requires the `keyring` library and first-time authentication:
```bash
# Install dependency (one-time)
pip install keyring

# Authenticate for the skill you need (opens browser)
python ~/.claude/skills/ai-skills/skills/google-chat/scripts/auth.py login
python ~/.claude/skills/ai-skills/skills/google-docs/scripts/auth.py login
python ~/.claude/skills/ai-skills/skills/google-sheets/scripts/auth.py login
python ~/.claude/skills/ai-skills/skills/google-slides/scripts/auth.py login
python ~/.claude/skills/ai-skills/skills/google-drive/scripts/auth.py login
python ~/.claude/skills/ai-skills/skills/google-calendar/scripts/auth.py login
python ~/.claude/skills/ai-skills/skills/gmail/scripts/auth.py login
```
Tokens stored securely via system keyring:
- **macOS**: Keychain
- **Windows**: Windows Credential Locker
- **Linux**: Secret Service API (GNOME Keyring, KDE Wallet, etc.)

## Usage

Once installed, skills activate automatically based on your requests. Just ask naturally:

### Postgres / MySQL / MSSQL
- "Query my production database for active users"
- "Show me the schema of the orders table"
- "How many signups last week?"
- "List tables in the MySQL staging database"
- "Show me the top 10 orders from SQL Server"

### Imagen
- "Generate an image of a sunset over mountains"
- "Create an app icon for my weather app"
- "I need a hero image for my landing page"

### Deep Research
- "Research the competitive landscape of EV batteries"
- "Compare React, Vue, and Angular frameworks"
- "What are the latest developments in Kubernetes?"

### Outline
- "Search the wiki for deployment guide"
- "Read the onboarding documentation"
- "Create a new wiki page for the API spec"

### Jules
- "Have Jules fix the authentication bug in src/auth.js"
- "Delegate adding unit tests to Jules"
- "Ask Jules to add documentation to the API module"
- "Check my Jules sessions" / "Pull the results from Jules"

### Manus
- "Use Manus to research the best 4K monitors for Mac"
- "Have Manus analyze AAPL stock with technical indicators"
- "Delegate market research on EV charging to Manus"
- "Ask Manus to compare AWS vs GCP vs Azure pricing"

### Grok Build
- "Use grok to implement this plan task-by-task"
- "Have grok build the CRUD endpoints from this spec"
- "Delegate the mechanical refactor in src/utils to grok"
- "Execute this implementation plan with grok"

### ElevenLabs
- "Narrate this PDF as audio"
- "Create a podcast from this document"
- "Convert this markdown file to speech"
- "List available ElevenLabs voices"

### Google TTS
- "Narrate this document using Google TTS"
- "Create a podcast from this analysis"
- "Convert this markdown to audio"
- "List available Google TTS voices"

### NotebookLM
- "Query this NotebookLM URL and summarize key points"
- "Add this NotebookLM link to library with topics"
- "Ask follow-up questions against my active notebook"

### Atlassian (Jira + Confluence)
- "Search Jira for open bugs in the DEV project"
- "Create a Jira task to fix the login bug"
- "Transition JDP-255 to Done"
- "Search Confluence for the deployment guide"
- "Read the SonarQube proposal page"

### Azure DevOps
- "List my Azure DevOps projects"
- "Create a bug work item in the Sandbox project"
- "Show open pull requests in the main repo"
- "Run the CI pipeline on the develop branch"
- "List pending deployment approvals"

### Google Workspace
- "List my Google Chat spaces" / "Send a message to Project Alpha"
- "Create a new Google Doc about the project proposal"
- "Get the content of my Q4 Budget spreadsheet"
- "What's on my calendar tomorrow?"
- "Search my Gmail for invoices from last month"
- "Find files named 'report' in my Drive"

## Skill Structure

All skills follow the [Agent Skills Standard](https://agentskills.io/specification):

```
skill-name/
├── SKILL.md              # Required: Instructions for the AI agent
├── README.md             # Human documentation
├── requirements.txt      # Dependencies (if any)
├── .env.example          # Environment variable template
└── scripts/              # Executable scripts
    └── main.py
```

The `SKILL.md` file uses YAML frontmatter:

```yaml
---
name: skill-name
description: "When to use this skill"
---

# Instructions for the AI agent
```

## Contributing

1. Fork this repository
2. Create a new skill in `skills/your-skill-name/`
3. Include `SKILL.md` with proper frontmatter
4. Add documentation in `README.md`
5. Submit a pull request

## Credits

- **Google Workspace Skills** - Based on the official [Google Workspace MCP server](https://github.com/gemini-cli-extensions/workspace) by the Gemini CLI team. Uses their OAuth cloud function for authentication.

## License

Apache-2.0

<!--
## Awesome Lists (for PR submissions when adding new skills)

| Repository | Fork | Notes |
|------------|------|-------|
| github.com/BehiSecc/awesome-claude-skills | sanjay3290/awesome-claude-skills-1 | Active, PRs merge quickly |
| github.com/travisvn/awesome-claude-skills | sanjay3290/awesome-claude-skills-3 | Uses table format for Individual Skills |
| github.com/Prat011/awesome-llm-skills | sanjay3290/awesome-llm-skills | Multi-LLM focus (Claude, Codex, Gemini, etc.) |
| github.com/ComposioHQ/awesome-claude-skills | sanjay3290/awesome-claude-skills | Composio-maintained, has connect-apps plugin |

Skill placement by category:
- postgres/mysql/mssql: Data & Analysis
- imagen: Creative & Media
- deep-research: Data & Analysis / Scientific & Research
- outline: Collaboration & Project Management
- jules: Development & Automation
- manus: Data & Analysis / Scientific & Research (deep research, market analysis)
- elevenlabs: Creative & Media
- google-tts: Creative & Media
- atlassian: Collaboration & Project Management (Jira + Confluence)
- azure-devops: Development & Automation
- apple-container: Development & Automation (containers on Apple-silicon macOS)
- telegram: Collaboration & Project Management (bot messaging, alerts, approvals)
- google-*: Collaboration & Project Management (all Google Workspace skills)
- gmail: Collaboration & Project Management
-->
