# GitHub Wiki Generator - Implementation Guide

## Project Overview

**Goal:** Build an automatic Wiki Generator for public GitHub repositories that organizes documentation by user-facing features (not technical layers) with inline citations linking back to source code.

**Time Budget:** ~5 hours of focused implementation

**Final Deliverable:** A deployed web app where users can input a GitHub repo URL and get a navigable wiki with cited documentation.

---

## ⚠️ COLLABORATIVE WORKFLOW - READ FIRST

**This project is being built collaboratively with a human partner.**

### How to Work

1. **STOP after completing each step** (Steps 1-15)
2. **Explain what you built** — Summarize the changes, files created/modified
3. **Explain key decisions** — Why you chose a particular approach, tradeoffs considered
4. **Flag any issues** — Blockers, uncertainties, deviations from the guide
5. **Ask for feedback** — Wait for human approval before proceeding to the next step
6. **After approval:**
   - Update this guide file to mark the step as ✅ COMPLETED
   - Commit all changes to git with a detailed commit message
   - Push to the remote repository

### Template for Each Step Completion

After completing a step, use this format:

```
## ✅ Step X Complete: [Step Name]

### What I Built
- [List of files created/modified]
- [Brief description of functionality added]

### Key Decisions Made
- [Decision 1]: [Why I chose this approach]
- [Decision 2]: [Tradeoffs considered]

### Issues/Concerns
- [Any blockers or uncertainties]
- [Deviations from the guide and why]

### Questions for You
- [Specific questions needing input]

---
Ready to proceed to Step X+1? Or would you like me to adjust anything?
```

### After Receiving Approval

Once the human approves a step, do the following **before** starting the next step:

**1. Update this guide file:**
- Find the step header (e.g., `### STEP 1: Project Setup`)
- Add `✅ COMPLETED` to the header (e.g., `### STEP 1: Project Setup ✅ COMPLETED`)
- If there were any deviations or notes, add them under the step

**2. Commit and push to git:**
```bash
git add .
git commit -m "<commit message>"
git push origin main
```

**3. Commit message format:**
```
Step X: [Step Name]

## What was implemented
- [File 1]: [What it does]
- [File 2]: [What it does]

## Key decisions
- [Decision 1]
- [Decision 2]

## Tests/Validation
- [What was tested and results]

## Notes
- [Any deviations from plan]
- [Known limitations]
```

**Example commit message:**
```
Step 2: GitHub Repo Fetching

## What was implemented
- src/lib/github/types.ts: Type definitions for RepoFile, RepoMetadata, FetchedRepo
- src/lib/github/fetch-repo.ts: GitHub API integration to fetch repo contents

## Key decisions
- Used GitHub Trees API with recursive=1 for single-request file listing
- Implemented file filtering: excluded node_modules, dist, files >100KB
- Added language detection based on file extension

## Tests/Validation
- Successfully fetched tastejs/todomvc (147 files after filtering)
- README extraction working
- Commit SHA correctly captured for permalink generation

## Notes
- Rate limit: 60 requests/hour unauthenticated
- Large repos may need pagination (not implemented yet)
```

### Important Rules

- **Do NOT proceed to the next step without explicit approval**
- **Do NOT assume answers to ambiguous requirements** — Ask first
- **Do NOT skip steps** — Even if they seem simple
- **Do NOT forget to commit after approval** — Every approved step must be committed and pushed
- **DO share your reasoning** — The human wants to understand your decisions
- **DO flag when you disagree with the guide** — Suggest alternatives if you see a better way
- **DO update this guide file** — Mark steps complete so progress is tracked

---

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | Next.js 14 (App Router) | SSR/SSG, API routes, easy deployment |
| Language | TypeScript | Type safety, better DX |
| Styling | Tailwind CSS | Fast iteration |
| AI | OpenAI SDK (`gpt-4o-mini`) | Required by challenge |
| Markdown | `react-markdown` + `remark-gfm` | Render wiki pages |
| Deployment | Vercel | Zero-config Next.js hosting |

---

## Project Structure

```
wiki-generator/
├── src/
│   ├── app/
│   │   ├── page.tsx                 # Home: repo URL input
│   │   ├── wiki/[repo]/
│   │   │   ├── page.tsx             # Wiki home/overview
│   │   │   └── [feature]/
│   │   │       └── page.tsx         # Feature page
│   │   └── api/
│   │       └── generate/
│   │           └── route.ts         # Main generation endpoint
│   │
│   ├── lib/
│   │   ├── github/
│   │   │   ├── fetch-repo.ts        # Download repo contents
│   │   │   ├── parse-structure.ts   # Build file tree
│   │   │   └── types.ts
│   │   │
│   │   ├── analysis/
│   │   │   ├── chunker.ts           # Split files into chunks
│   │   │   ├── signals.ts           # Extract entry points
│   │   │   ├── imports.ts           # Parse import relationships
│   │   │   └── types.ts
│   │   │
│   │   ├── ai/
│   │   │   ├── openai.ts            # OpenAI client setup
│   │   │   ├── propose-features.ts  # Feature proposal prompt
│   │   │   ├── generate-page.ts     # Wiki page generation
│   │   │   └── prompts.ts           # Prompt templates
│   │   │
│   │   ├── wiki/
│   │   │   ├── evidence.ts          # Gather evidence per feature
│   │   │   ├── citations.ts         # Process citations to links
│   │   │   └── types.ts
│   │   │
│   │   └── store/
│   │       └── wiki-store.ts        # In-memory store for generated wikis
│   │
│   └── components/
│       ├── WikiSidebar.tsx
│       ├── WikiPage.tsx
│       ├── CitationLink.tsx
│       ├── SearchBar.tsx
│       └── LoadingState.tsx
│
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── .env.local                       # OPENAI_API_KEY
```

---

## Implementation Steps

Complete these steps IN ORDER. Each step has acceptance criteria that must pass before moving on.

> **🛑 REMINDER:** After completing each step, STOP and report your progress using the template above. Wait for approval before continuing.

---

### STEP 1: Project Setup

**Goal:** Initialize the project with all dependencies and configuration.

**Tasks:**
```bash
# 1.1 Create Next.js project
npx create-next-app@latest wiki-generator --typescript --tailwind --eslint --app --src-dir

# 1.2 Install dependencies
cd wiki-generator
npm install openai react-markdown remark-gfm
npm install -D @types/node

# 1.3 Create .env.local (get API key from user)
echo "OPENAI_API_KEY=<your-api-key>" > .env.local

# 1.4 Initialize git and push to GitHub
git init
git add .
git commit -m "Initial commit: Next.js project setup"
git remote add origin <github-repo-url>  # Ask human for repo URL
git push -u origin main

# 1.5 Add this IMPLEMENTATION_GUIDE.md to the repo root
cp /path/to/IMPLEMENTATION_GUIDE.md ./IMPLEMENTATION_GUIDE.md
git add IMPLEMENTATION_GUIDE.md
git commit -m "Add implementation guide"
git push
```

**Note:** Ask the human for:
- The OpenAI API key to put in `.env.local`
- The GitHub repository URL for the project

**Acceptance Criteria:**
- [ ] `npm run dev` starts without errors
- [ ] Can access `localhost:3000`
- [ ] TypeScript compiles without errors
- [ ] Git repo initialized and pushed to GitHub
- [ ] IMPLEMENTATION_GUIDE.md is in the repo root

> **🛑 CHECKPOINT:** Stop here. Report what you've set up, any issues encountered, and wait for approval before Step 2.

---

### STEP 2: GitHub Repo Fetching

**Goal:** Fetch repository contents via GitHub API (no auth needed for public repos).

**File:** `src/lib/github/fetch-repo.ts`

**Tasks:**

2.1 Create types:
```typescript
// src/lib/github/types.ts
export interface RepoFile {
  path: string;
  content: string;
  size: number;
  language: string | null;
}

export interface RepoMetadata {
  owner: string;
  repo: string;
  defaultBranch: string;
  commitSha: string;
  description: string | null;
}

export interface FetchedRepo {
  metadata: RepoMetadata;
  files: RepoFile[];
  readme: string | null;
}
```

2.2 Implement fetcher:
```typescript
// src/lib/github/fetch-repo.ts
// Use GitHub API: GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
// Then fetch individual file contents for relevant files
// Filter OUT: node_modules, dist, build, .git, binaries, images, lockfiles
// Filter IN: .ts, .tsx, .js, .jsx, .py, .go, .rs, .md, .json (config only)
// Limit: Skip files > 100KB
```

2.3 Implement language detection:
```typescript
// Simple extension-based detection
function detectLanguage(path: string): string | null {
  const ext = path.split('.').pop();
  const langMap: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript',
    js: 'javascript', jsx: 'javascript',
    py: 'python', go: 'go', rs: 'rust',
    // ... etc
  };
  return langMap[ext || ''] || null;
}
```

**Acceptance Criteria:**
- [ ] Can fetch `https://github.com/tastejs/todomvc` structure
- [ ] Returns file list with paths and content
- [ ] Correctly filters out node_modules, binaries
- [ ] Extracts README content
- [ ] Returns commit SHA for stable links

**Test:**
```typescript
const repo = await fetchRepo('tastejs', 'todomvc');
console.log(repo.files.length); // Should be reasonable (not thousands)
console.log(repo.readme?.substring(0, 100)); // Should have content
console.log(repo.metadata.commitSha); // Should be 40-char hash
```

> **🛑 CHECKPOINT:** Stop here. This is a critical foundation step. Share your implementation approach, how you handled rate limits, and test results.

---

### STEP 3: File Chunking

**Goal:** Split files into semantic chunks with line number tracking.

**File:** `src/lib/analysis/chunker.ts`

**Types:**
```typescript
// src/lib/analysis/types.ts
export interface CodeChunk {
  id: string;              // e.g., "src/auth/login.ts:15-45"
  filePath: string;
  startLine: number;
  endLine: number;
  content: string;
  language: string | null;
}
```

**Implementation Strategy:**

3.1 Try semantic chunking first (regex-based, not full AST):
```typescript
// For JS/TS: Split on function/class declarations
const JS_CHUNK_PATTERNS = [
  /^export\s+(default\s+)?(async\s+)?function\s+\w+/m,
  /^export\s+(default\s+)?class\s+\w+/m,
  /^(async\s+)?function\s+\w+/m,
  /^class\s+\w+/m,
  /^export\s+const\s+\w+\s*=/m,
  /^const\s+\w+\s*=\s*(async\s+)?\(/m,  // arrow functions
];
```

3.2 Fall back to line-based chunking:
```typescript
// If no patterns match, chunk by ~60 lines with 10 line overlap
function chunkByLines(content: string, chunkSize = 60, overlap = 10): ChunkRange[]
```

3.3 Generate chunk IDs:
```typescript
function makeChunkId(filePath: string, startLine: number, endLine: number): string {
  return `${filePath}:${startLine}-${endLine}`;
}
```

**Acceptance Criteria:**
- [ ] JavaScript files are split on function boundaries when possible
- [ ] Each chunk has accurate line numbers
- [ ] Chunk IDs are unique and parseable
- [ ] No chunk exceeds 100 lines (soft limit)
- [ ] All file content is covered (no gaps)

**Test:**
```typescript
const chunks = chunkFile({
  path: 'src/auth.ts',
  content: `
function login(user, pass) {
  // 20 lines of code
}

function logout() {
  // 15 lines of code
}

export class AuthService {
  // 40 lines of code
}
`,
  language: 'typescript'
});

// Should produce 3 chunks: login, logout, AuthService
expect(chunks.length).toBe(3);
expect(chunks[0].id).toMatch(/src\/auth\.ts:\d+-\d+/);
```

---

### STEP 4: Signal Extraction

**Goal:** Identify entry points and user-facing surfaces WITHOUT using LLM.

**File:** `src/lib/analysis/signals.ts`

**Types:**
```typescript
export interface Signals {
  // User-facing
  readmeSections: { title: string; content: string }[];
  cliCommands: { name: string; file: string }[];
  apiRoutes: { method: string; path: string; file: string }[];
  
  // Backend
  scheduledTasks: { name: string; file: string }[];
  queueWorkers: { name: string; file: string }[];
  
  // Structure
  entryPoints: { name: string; file: string }[];  // main, index, app
  configFiles: string[];
}
```

**Implementation:**

4.1 Parse README sections:
```typescript
// Split README.md by ## headings
// Extract sections: "Features", "Usage", "Commands", "API", "Installation"
function parseReadmeSections(readme: string): { title: string; content: string }[]
```

4.2 Detect CLI commands:
```typescript
// Look for patterns in files:
// - commander: .command('name')
// - yargs: .command('name', ...)
// - argparse: add_subparsers, add_parser('name')
// - package.json "bin" field
const CLI_PATTERNS = [
  /\.command\(['"](\w+)['"]/g,
  /program\.command\(['"]([^'"]+)['"]/g,
];
```

4.3 Detect API routes:
```typescript
// Express: app.get('/path', ...), router.post('/path', ...)
// Next.js: file path in app/api/ or pages/api/
// FastAPI: @app.get("/path"), @router.post("/path")
const ROUTE_PATTERNS = [
  /\.(get|post|put|delete|patch)\(['"]([^'"]+)['"]/g,
  /@(app|router)\.(get|post|put|delete)\(['"]([^'"]+)['"]/g,
];
```

4.4 Detect backend tasks:
```typescript
// Cron: node-cron, @Scheduled, schedule.scheduleJob
// Queues: Bull, BullMQ, Celery, Sidekiq patterns
// File names: worker.ts, jobs/*.ts, tasks/*.py
const BACKEND_PATTERNS = {
  cron: [/cron\.schedule\(/, /@Scheduled/, /scheduleJob\(/],
  queue: [/new Queue\(/, /Worker\(/, /@celery\.task/],
};
```

4.5 Find entry points:
```typescript
// main.ts, index.ts, app.ts, server.ts, cli.ts
// package.json "main" field
// __main__.py, app.py, manage.py
const ENTRY_POINT_NAMES = [
  'main', 'index', 'app', 'server', 'cli', '__main__', 'manage'
];
```

**Acceptance Criteria:**
- [ ] Extracts README sections with titles
- [ ] Finds CLI commands from commander/yargs/argparse
- [ ] Finds API routes from Express/FastAPI patterns
- [ ] Identifies entry point files
- [ ] Works on at least JS/TS and Python files

**Test:**
```typescript
const signals = extractSignals(repoFiles, readme);

// For a CLI tool like rich-cli:
expect(signals.cliCommands.length).toBeGreaterThan(0);

// For an API like browser-use:
expect(signals.entryPoints.length).toBeGreaterThan(0);
```

> **🛑 CHECKPOINT:** Stop here. Signal extraction is crucial for feature quality. Share what patterns you implemented and test results on a sample repo.

---

### STEP 5: Import/Dependency Parsing

**Goal:** Build a simple file-level dependency graph for evidence gathering.

**File:** `src/lib/analysis/imports.ts`

**Types:**
```typescript
export interface ImportGraph {
  nodes: string[];  // file paths
  edges: { from: string; to: string }[];
}
```

**Implementation:**

5.1 Parse imports:
```typescript
// JavaScript/TypeScript
const JS_IMPORT_PATTERNS = [
  /import\s+.*\s+from\s+['"]([^'"]+)['"]/g,
  /require\(['"]([^'"]+)['"]\)/g,
  /import\(['"]([^'"]+)['"]\)/g,  // dynamic import
];

// Python
const PY_IMPORT_PATTERNS = [
  /^import\s+([\w.]+)/gm,
  /^from\s+([\w.]+)\s+import/gm,
];
```

5.2 Resolve relative imports:
```typescript
// './utils' from 'src/auth/login.ts' -> 'src/auth/utils.ts' or 'src/auth/utils/index.ts'
function resolveImport(importPath: string, fromFile: string, allFiles: string[]): string | null
```

5.3 Build graph:
```typescript
function buildImportGraph(files: RepoFile[]): ImportGraph
```

**Acceptance Criteria:**
- [ ] Parses ES6 imports, CommonJS requires
- [ ] Resolves relative imports to actual file paths
- [ ] Ignores external packages (node_modules)
- [ ] Returns valid graph structure

**Test:**
```typescript
const graph = buildImportGraph(files);
// If auth/login.ts imports auth/session.ts:
expect(graph.edges).toContainEqual({
  from: 'src/auth/login.ts',
  to: 'src/auth/session.ts'
});
```

---

### STEP 6: OpenAI Client Setup

**Goal:** Configure OpenAI client with proper error handling.

**File:** `src/lib/ai/openai.ts`

```typescript
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function complete(
  systemPrompt: string,
  userPrompt: string,
  options?: { temperature?: number; maxTokens?: number }
): Promise<string> {
  const response = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: options?.temperature ?? 0.3,
    max_tokens: options?.maxTokens ?? 2000,
  });
  
  return response.choices[0]?.message?.content || '';
}

export async function completeJSON<T>(
  systemPrompt: string,
  userPrompt: string
): Promise<T> {
  const response = await complete(
    systemPrompt + '\n\nRespond with valid JSON only. No markdown, no explanation.',
    userPrompt,
    { temperature: 0.2 }
  );
  
  // Strip markdown code blocks if present
  const cleaned = response.replace(/```json\n?|\n?```/g, '').trim();
  return JSON.parse(cleaned) as T;
}
```

**Acceptance Criteria:**
- [ ] Can make successful API calls
- [ ] Handles JSON responses
- [ ] Proper error handling for rate limits/failures

---

### STEP 7: Feature Proposal (LLM)

**Goal:** Use LLM to propose user-facing features based on signals.

**File:** `src/lib/ai/propose-features.ts`

**Types:**
```typescript
export interface ProposedFeature {
  id: string;           // slug: "user-authentication"
  title: string;        // "User Authentication"
  description: string;  // 1-2 sentence summary
  userStory: string;    // "As a user, I can..."
  entryPoints: string[];  // file paths that start this feature
  keywords: string[];   // for evidence search
}

export interface FeatureProposal {
  repoSummary: string;  // What this repo does
  features: ProposedFeature[];
}
```

**Prompt:**
```typescript
const SYSTEM_PROMPT = `You are a senior software architect analyzing a codebase to create developer documentation.

Your task is to identify USER-FACING FEATURES, not technical layers.

BAD groupings (avoid these):
- "Frontend", "Backend", "API", "Utils", "Helpers", "Components"

GOOD groupings (aim for these):
- "User Authentication" (login, signup, sessions)
- "Document Export" (PDF generation, sharing)
- "Search & Filtering" (query builder, facets)
- "Background Jobs" (email sending, data sync)

Each feature should represent something a USER or DEVELOPER can DO with the software.`;

const USER_PROMPT = `
# Repository: {repoName}

## Description
{repoDescription}

## README Sections
{readmeSections}

## Entry Points Found
{entryPoints}

## CLI Commands
{cliCommands}

## API Routes
{apiRoutes}

## File Structure (top-level)
{fileTree}

---

Based on this analysis, propose 5-9 user-facing features for this codebase.

Respond in JSON:
{
  "repoSummary": "One paragraph describing what this software does",
  "features": [
    {
      "id": "feature-slug",
      "title": "Feature Title",
      "description": "What this feature does",
      "userStory": "As a [user type], I can [action] so that [benefit]",
      "entryPoints": ["src/path/to/entry.ts"],
      "keywords": ["relevant", "search", "terms"]
    }
  ]
}
`;
```

**Acceptance Criteria:**
- [ ] Returns 5-9 features for typical repos
- [ ] Features are user-facing, not technical layers
- [ ] Each feature has entry points mapped to real files
- [ ] JSON parses correctly

**Test:**
```typescript
const proposal = await proposeFeatures(signals, fileTree);
expect(proposal.features.length).toBeGreaterThanOrEqual(3);
expect(proposal.features[0].entryPoints.length).toBeGreaterThan(0);
// Should NOT have features named "Utils", "Helpers", "Components"
proposal.features.forEach(f => {
  expect(f.title.toLowerCase()).not.toMatch(/util|helper|component|frontend|backend/);
});
```

> **🛑 CHECKPOINT:** Stop here. This is the first LLM integration. Share the exact prompt you used, sample output, and whether features are truly user-facing.

---

### STEP 8: Evidence Gathering

**Goal:** For each feature, collect relevant code chunks using entry points + import graph.

**File:** `src/lib/wiki/evidence.ts`

**Types:**
```typescript
export interface FeatureEvidence {
  featureId: string;
  chunks: CodeChunk[];
  filesCovered: string[];
}
```

**Implementation:**

8.1 Seed from entry points:
```typescript
function getEntryPointChunks(
  feature: ProposedFeature,
  allChunks: CodeChunk[]
): CodeChunk[]
```

8.2 Expand via imports (bounded):
```typescript
function expandByImports(
  seedFiles: string[],
  graph: ImportGraph,
  allChunks: CodeChunk[],
  maxHops: number = 2,
  maxChunks: number = 30
): CodeChunk[]
```

8.3 Add keyword matches:
```typescript
function findByKeywords(
  keywords: string[],
  allChunks: CodeChunk[],
  limit: number = 10
): CodeChunk[]
```

8.4 Combine and dedupe:
```typescript
export function gatherEvidence(
  feature: ProposedFeature,
  allChunks: CodeChunk[],
  graph: ImportGraph
): FeatureEvidence {
  const seedChunks = getEntryPointChunks(feature, allChunks);
  const seedFiles = [...new Set(seedChunks.map(c => c.filePath))];
  
  const expandedChunks = expandByImports(seedFiles, graph, allChunks, 2, 30);
  const keywordChunks = findByKeywords(feature.keywords, allChunks, 10);
  
  // Combine, dedupe, limit to 40 chunks max
  const allEvidence = dedupeChunks([...seedChunks, ...expandedChunks, ...keywordChunks]);
  return {
    featureId: feature.id,
    chunks: allEvidence.slice(0, 40),
    filesCovered: [...new Set(allEvidence.map(c => c.filePath))],
  };
}
```

**Acceptance Criteria:**
- [ ] Returns chunks for each feature
- [ ] Respects max chunk limits
- [ ] Includes entry point chunks
- [ ] Expands to imported files
- [ ] No duplicate chunks

---

### STEP 9: Wiki Page Generation (LLM)

**Goal:** Generate markdown documentation for each feature with inline citations.

**File:** `src/lib/ai/generate-page.ts`

**Prompt:**
```typescript
const SYSTEM_PROMPT = `You are a technical writer creating developer documentation.

Write clear, accurate documentation with INLINE CITATIONS to source code.

Citation format: [filename:startLine-endLine]
Example: "The login flow begins in [src/auth/login.ts:45-67] which validates credentials..."

EVERY technical claim must have a citation. If you can't cite it, don't say it.

Structure your documentation with:
1. Overview (what this feature does, who it's for)
2. How it works (step-by-step flow with citations)
3. Key components (important functions/classes with citations)
4. Usage examples (if evident from code)`;

const USER_PROMPT = `
# Feature: {featureTitle}

## Description
{featureDescription}

## User Story
{userStory}

## Source Code Evidence

{chunks.map(chunk => `
### [{chunk.id}]
\`\`\`{chunk.language}
{chunk.content}
\`\`\`
`).join('\n')}

---

Write comprehensive documentation for this feature.
Use [chunkId] citations for every technical claim.
`;
```

**Post-processing:**
```typescript
// src/lib/wiki/citations.ts

export function processCitations(
  markdown: string,
  chunks: CodeChunk[],
  repoMeta: RepoMetadata
): string {
  // Match [filepath:start-end] patterns
  const citationRegex = /\[([^\]]+):(\d+)-(\d+)\]/g;
  
  return markdown.replace(citationRegex, (match, filePath, start, end) => {
    // Build GitHub permalink
    const url = `https://github.com/${repoMeta.owner}/${repoMeta.repo}/blob/${repoMeta.commitSha}/${filePath}#L${start}-L${end}`;
    const shortName = filePath.split('/').pop();
    return `[\`${shortName}:${start}-${end}\`](${url})`;
  });
}
```

**Acceptance Criteria:**
- [ ] Generates readable markdown
- [ ] Includes citations in [file:line-line] format
- [ ] Citations are converted to GitHub links
- [ ] All sections present (overview, how it works, components)
- [ ] No hallucinated file paths

**Test:**
```typescript
const page = await generatePage(feature, evidence, repoMeta);
// Should contain citations
expect(page).toMatch(/\[`[\w.]+:\d+-\d+`\]\(https:\/\/github\.com/);
// Should have sections
expect(page).toMatch(/## Overview|## How it works/i);
```

> **🛑 CHECKPOINT:** Stop here. This is the core output. Share a sample generated page, verify citations are accurate, and get feedback on quality.

---

### STEP 10: In-Memory Wiki Store

**Goal:** Store generated wikis for serving (no database needed for MVP).

**File:** `src/lib/store/wiki-store.ts`

```typescript
export interface GeneratedWiki {
  repoId: string;          // "owner/repo"
  metadata: RepoMetadata;
  summary: string;
  features: {
    id: string;
    title: string;
    description: string;
    content: string;       // processed markdown
  }[];
  generatedAt: Date;
}

// Simple in-memory store (resets on deploy, fine for MVP)
const wikiStore = new Map<string, GeneratedWiki>();

export function saveWiki(wiki: GeneratedWiki): void {
  wikiStore.set(wiki.repoId, wiki);
}

export function getWiki(repoId: string): GeneratedWiki | null {
  return wikiStore.get(repoId) || null;
}

export function listWikis(): string[] {
  return Array.from(wikiStore.keys());
}
```

---

### STEP 11: API Route - Generate Wiki

**Goal:** Create endpoint that orchestrates the full pipeline.

**File:** `src/app/api/generate/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  const { repoUrl } = await request.json();
  
  // 1. Parse repo URL
  const { owner, repo } = parseGitHubUrl(repoUrl);
  
  // 2. Check if already generated
  const existing = getWiki(`${owner}/${repo}`);
  if (existing) {
    return NextResponse.json({ wiki: existing, cached: true });
  }
  
  // 3. Fetch repo
  const fetchedRepo = await fetchRepo(owner, repo);
  
  // 4. Chunk files
  const chunks = fetchedRepo.files.flatMap(f => chunkFile(f));
  
  // 5. Extract signals
  const signals = extractSignals(fetchedRepo.files, fetchedRepo.readme);
  
  // 6. Build import graph
  const graph = buildImportGraph(fetchedRepo.files);
  
  // 7. Propose features (LLM)
  const proposal = await proposeFeatures(signals, fetchedRepo);
  
  // 8. For each feature: gather evidence + generate page
  const features = await Promise.all(
    proposal.features.map(async (feature) => {
      const evidence = gatherEvidence(feature, chunks, graph);
      const rawContent = await generatePage(feature, evidence, fetchedRepo.metadata);
      const content = processcitations(rawContent, chunks, fetchedRepo.metadata);
      
      return {
        id: feature.id,
        title: feature.title,
        description: feature.description,
        content,
      };
    })
  );
  
  // 9. Save and return
  const wiki: GeneratedWiki = {
    repoId: `${owner}/${repo}`,
    metadata: fetchedRepo.metadata,
    summary: proposal.repoSummary,
    features,
    generatedAt: new Date(),
  };
  
  saveWiki(wiki);
  
  return NextResponse.json({ wiki, cached: false });
}
```

**Acceptance Criteria:**
- [ ] Accepts GitHub URL in POST body
- [ ] Returns complete wiki structure
- [ ] Handles errors gracefully
- [ ] Caches results to avoid re-generation

> **🛑 CHECKPOINT:** Stop here. The full pipeline is now connected. Test end-to-end with a real repo and share results before building UI.

---

### STEP 12: Frontend - Home Page

**Goal:** Simple form to input GitHub repo URL.

**File:** `src/app/page.tsx`

**Requirements:**
- Input field for GitHub URL
- "Generate Wiki" button
- Loading state during generation
- Error handling
- Redirect to wiki on success

**UI Sketch:**
```
┌─────────────────────────────────────────────┐
│                                             │
│         📚 GitHub Wiki Generator            │
│                                             │
│   Generate documentation for any public     │
│   GitHub repository                         │
│                                             │
│   ┌─────────────────────────────────────┐   │
│   │ https://github.com/owner/repo       │   │
│   └─────────────────────────────────────┘   │
│                                             │
│          [ Generate Wiki ]                  │
│                                             │
│   Example repos to try:                     │
│   • tastejs/todomvc                         │
│   • Textualize/rich-cli                     │
│   • browser-use/browser-use                 │
│                                             │
└─────────────────────────────────────────────┘
```

---

### STEP 13: Frontend - Wiki Layout

**Goal:** Display generated wiki with sidebar navigation.

**Files:**
- `src/app/wiki/[owner]/[repo]/layout.tsx` - Sidebar layout
- `src/app/wiki/[owner]/[repo]/page.tsx` - Wiki home/overview
- `src/app/wiki/[owner]/[repo]/[feature]/page.tsx` - Feature page

**Layout Structure:**
```
┌──────────────────┬──────────────────────────────────────┐
│                  │                                      │
│  📚 repo-name    │   Feature Title                      │
│                  │                                      │
│  Overview        │   ## Overview                        │
│                  │   Description text with citations    │
│  Features        │   that link to GitHub source.        │
│  ├─ Auth         │                                      │
│  ├─ API          │   ## How it works                    │
│  ├─ CLI          │   Step-by-step explanation...        │
│  └─ Export       │                                      │
│                  │   ## Key Components                  │
│  ──────────────  │   - `function` - description         │
│  🔍 Search       │                                      │
│                  │                                      │
└──────────────────┴──────────────────────────────────────┘
```

**Components Needed:**

```typescript
// src/components/WikiSidebar.tsx
// - Repo name + link
// - "Overview" link
// - List of features (active state)
// - Optional search input

// src/components/WikiPage.tsx
// - Render markdown with react-markdown
// - Style code blocks
// - Style citation links (highlight on hover)

// src/components/CitationLink.tsx
// - Styled link to GitHub
// - Shows file:lines on hover
// - Opens in new tab
```

**Acceptance Criteria:**
- [ ] Sidebar shows all features
- [ ] Active feature is highlighted
- [ ] Markdown renders correctly
- [ ] Code blocks have syntax highlighting
- [ ] Citation links work and go to GitHub
- [ ] Responsive on mobile

> **🛑 CHECKPOINT:** Stop here. Share screenshots of the UI, get feedback on layout/styling before adding loading states.

---

### STEP 14: Loading & Error States

**Goal:** Good UX during generation (which takes 30-60 seconds).

**Requirements:**
- Show progress steps during generation
- Handle API errors gracefully
- Allow retry on failure

**Loading UI:**
```
┌─────────────────────────────────────────────┐
│                                             │
│   Generating wiki for owner/repo...         │
│                                             │
│   ✓ Fetching repository                     │
│   ✓ Analyzing code structure                │
│   ⏳ Identifying features...                │
│   ○ Generating documentation                │
│   ○ Processing citations                    │
│                                             │
│   This may take 30-60 seconds               │
│                                             │
└─────────────────────────────────────────────┘
```

---

### STEP 15: Deploy to Vercel

**Goal:** Get publicly accessible URL.

**Tasks:**
```bash
# 15.1 Push to GitHub
git init
git add .
git commit -m "Initial commit: GitHub Wiki Generator"
git remote add origin https://github.com/YOUR_USERNAME/wiki-generator.git
git push -u origin main

# 15.2 Deploy to Vercel
# - Go to vercel.com
# - Import your GitHub repo
# - Add environment variable: OPENAI_API_KEY
# - Deploy
```

**Acceptance Criteria:**
- [ ] App accessible at `your-app.vercel.app`
- [ ] Can generate wiki for `tastejs/todomvc`
- [ ] Wiki displays correctly
- [ ] Citations link to correct GitHub lines

> **🛑 FINAL CHECKPOINT:** Stop here. Share the deployed URL, run through the full testing checklist together, and discuss any final polish needed.

---

## Testing Checklist

Run these tests before considering the project complete:

### Functional Tests

| Test | Steps | Expected |
|------|-------|----------|
| Basic generation | Enter `https://github.com/tastejs/todomvc`, click Generate | Wiki generated with 3+ features |
| Citation links | Click any citation in generated wiki | Opens GitHub at correct file and lines |
| Feature navigation | Click different features in sidebar | Content changes, URL updates |
| Cached results | Generate same repo twice | Second time is instant |
| Invalid URL | Enter `https://github.com/nonexistent/repo` | Shows error message |

### Quality Tests

| Test | Check |
|------|-------|
| Features are user-facing | No features named "Utils", "Helpers", "Components" |
| Citations are accurate | At least 3 citations per page link to real code |
| Content is useful | Overview explains what feature does, not just lists files |
| No hallucinations | Every cited file exists in the repo |

### Repos to Test

1. `tastejs/todomvc` - Multi-framework examples
2. `Textualize/rich-cli` - Python CLI tool  
3. `browser-use/browser-use` - Python library

---

## Known Limitations (Document in Reflection)

1. **No persistent storage** - Wikis are lost on redeploy
2. **Rate limits** - GitHub API (60/hr unauthenticated), OpenAI
3. **Large repos** - May timeout or hit token limits
4. **Dynamic imports** - Not traced in dependency graph
5. **Non-JS/Python** - Limited signal detection for other languages
6. **Private repos** - Not supported (no auth)
7. **Monorepos** - May produce too many features

---

## Extension Ideas (Bonus, Time Permitting)

1. **Q&A Chat** - Ask questions about the wiki
2. **Search** - Full-text search across pages
3. **Export** - Download wiki as markdown/PDF
4. **Refresh** - Re-generate when repo updates
5. **Diff view** - Show what changed between generations

---

## File-by-File Implementation Order

For maximum efficiency, implement in this order. **Remember: Stop after each STEP (not each file) for review.**

| Step | Files | Checkpoint? | Status |
|------|-------|-------------|--------|
| 1 | Project setup | ✅ Yes | ⬜ Pending |
| 2 | `types.ts`, `fetch-repo.ts` | ✅ Yes | ⬜ Pending |
| 3 | `types.ts`, `chunker.ts` | Yes | ⬜ Pending |
| 4 | `signals.ts` | ✅ Yes | ⬜ Pending |
| 5 | `imports.ts` | Yes | ⬜ Pending |
| 6 | `openai.ts` | Yes | ⬜ Pending |
| 7 | `propose-features.ts` | ✅ Yes | ⬜ Pending |
| 8 | `evidence.ts` | Yes | ⬜ Pending |
| 9 | `generate-page.ts`, `citations.ts` | ✅ Yes | ⬜ Pending |
| 10 | `wiki-store.ts` | Yes | ⬜ Pending |
| 11 | `api/generate/route.ts` | ✅ Yes | ⬜ Pending |
| 12 | `page.tsx` (home) | Yes | ⬜ Pending |
| 13 | Components + wiki pages | ✅ Yes | ⬜ Pending |
| 14 | Loading states | Yes | ⬜ Pending |
| 15 | Deploy | ✅ Yes | ⬜ Pending |

**Status Legend:**
- ⬜ Pending — Not started
- 🔄 In Progress — Currently working on
- ✅ Completed — Approved and committed

---

## Quick Reference: Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Chunking strategy | Semantic (regex) with line fallback | Better chunks without AST complexity |
| Feature discovery | Signals-first (no code clustering) | More accurate user-facing features |
| Evidence gathering | Entry points + 2-hop imports + keywords | Bounded, relevant |
| Citation format | `[file:start-end]` → GitHub permalink | Simple, verifiable |
| Storage | In-memory Map | Fast for MVP, no DB setup |
| Styling | Tailwind | Fast iteration |

---

Good luck! Work through the steps in order, test each one, and you'll have a working wiki generator.

---

## Final Reminder

**This is a collaborative project.** Your human partner wants to:
- Understand your decisions
- Catch issues early
- Learn from your approach
- Provide course corrections

**Never proceed without approval.** When in doubt, ask. It's better to over-communicate than to build the wrong thing.

Start with Step 1, complete it, report back, and wait for the green light. Let's build this together! 🚀
