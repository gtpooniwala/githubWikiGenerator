# Pipeline Architecture, Audit, and Improvement Options

This document has three goals:

1. Explain the **current end-to-end pipeline architecture and logic** (as implemented)
2. Audit where quality, recall, and reliability are currently constrained
3. Propose **worthwhile** improvements and alternate approaches with tradeoffs

It complements:

- [README.md](README.md) for concise project summary
- [guide.md](guide.md) for execution spec and stage sequencing

---

## Scope

This doc focuses on pipeline logic and documentation quality:

- Retrieval quality (chunking, graph traversal, evidence assembly)
- Feature proposal quality
- Citation correctness and trust
- Architectural alternatives and tradeoffs

Operational concerns (parallelization, caching, queueing, autoscaling) are still important, but not the focus of this document.

---

## Current pipeline architecture and logic (full walkthrough)

The pipeline runs deterministically against one commit SHA and returns `GenerateResponse`.

## Stage 0 — Parse and normalize repo identity

- Input: GitHub URL (`https://github.com/owner/repo`)
- Logic: parse owner/repo, validate URL shape
- Output: `(owner, repo)` identifiers used by all downstream stages

## Stage 1 — Load repository snapshot (GitHub API)

- Service: `repo_loader.py`
- Logic:
  1. Fetch repo metadata and default branch
  2. Resolve branch head commit SHA
  3. Fetch recursive tree
  4. Filter files (`file_filter.py`) by size/path/type
  5. Download candidate file contents at the pinned SHA
- Output: `RepoSnapshot(owner, repo, commit_sha, files, readme?)`

Why this matters:

- Every citation and page is anchored to one immutable commit
- Filtering early controls cost and downstream token pressure

## Stage 2 — Extract deterministic repository signals

- Service: `signals.py`
- Signals extracted:
  - README headings
  - HTTP routes (FastAPI/Express/Next.js patterns)
  - Entrypoints (`package.json` scripts, Python `__main__`, CLI modules)
- Output: `RepoSignals`

Why this matters:

- These signals are compact and high-value context for feature proposal
- This stage is non-LLM and deterministic

## Stage 3 — Chunk source files into citation units

- Service: `chunker.py`
- Current strategy:
  - Base: sliding window chunks (`WINDOW_SIZE=60`, `OVERLAP=10`)
  - Python/JS/TS: regex semantic boundaries (`def`, `class`, `function`, `export`, etc.)
  - Long semantic blocks are sub-chunked back to windows
- Output: `Chunk[]` with deterministic IDs (`path:start-end`)

Why this matters:

- Chunk quality directly controls evidence precision and citation quality

## Stage 4 — Build file-level import graph

- Service: `import_graph.py`
- Current strategy:
  - Regex parse imports for Python and JS/TS
  - Resolve only intra-repo paths
  - Build adjacency list `file -> [imported_files]`
- Output: `ImportGraph`

Why this matters:

- Graph traversal expands evidence beyond seed files

## Stage 5 — Build lexical search index

- Service: `search_index.py`
- Strategy: BM25 over chunk text, with substring fallback when BM25 has no hits
- Output: in-memory `SearchIndex`

Why this matters:

- Provides query-based recovery beyond graph adjacency

## Stage 6 — Propose user-facing features (LLM)

- Service: `propose_features.py`
- Inputs to prompt:
  - Repo identity + commit
  - README headings
  - Routes
  - Entrypoints
  - Trimmed file list
- Output: 5–9 `FeatureProposal` items (`id`, `title`, `description`, `seed_paths`)
- Post-processing:
  - Ban infra-layer titles (e.g., “utils”, “frontend”, “backend”)
  - Slug normalization

Why this matters:

- Seed paths drive evidence retrieval, so this stage heavily influences downstream quality

## Stage 7 — Gather per-feature evidence

- Service: `evidence.py`
- Current logic (per feature):
  1. Start from `seed_paths`
  2. Expand via outgoing import-graph BFS (`max_hops=2`)
  3. Add BM25 top-k hits (`k=20`)
  4. Deduplicate by `chunk_id`
  5. Deterministically sort (seed-first, then path/line)
  6. Cap evidence (`max_chunks=40`, `max_chars=80,000`)
- Output: `EvidencePack`

Why this matters:

- This stage decides what context the writer LLM sees

## Stage 8 — Write feature pages with inline citations (LLM x N)

- Service: `write_pages.py`
- Prompt receives evidence chunks and must cite in `[path:start-end]`
- Post-process: `citations.py` resolves citations to GitHub permalinks
- Output: `WikiFeature[]`

Why this matters:

- Final user-facing quality and trust depend on this stage

## Stage 9 — Write repository overview page (LLM)

- Service: `write_pages.py`
- Uses constrained evidence set: README + manifests + entrypoint files
- Produces architecture/quickstart summary with citations
- Output: `overview_md`

Why this matters:

- Keeps overview high-level and avoids implementation noise

## Stage 10 — Assemble and return response

- Service: `pipeline.py` / SSE router
- Output: `GenerateResponse(repo_id, commit_sha, overview_md, features)`
- SSE mode streams each completed stage and sends full payload in `done`

Why this matters:

- Frontend can render immediately from the `done` payload without extra round-trip

---

## Implementation audit: what is working well

1. **Deterministic core flow**
   - Stable chunk IDs and deterministic sorting improve reproducibility

2. **Pinned-commit grounding**
   - Citation links are commit-anchored and stable over time

3. **Good cost/complexity balance for challenge scope**
   - BM25 + import graph + bounded evidence is pragmatic and robust

4. **Memory-aware optimization exists already**
   - Raw file contents are dropped after chunking for non-overview files

---

## Implementation audit: high-value gaps worth documenting

## A) Chunking fidelity is uneven

- Regex semantic boundaries do not fully model language structure
- Nested methods/blocks and long segments can still be cut at arbitrary points
- Non Python/JS/TS files get no semantic splitting

Result:

- Mixed-topic chunks
- Lower citation locality
- Noise in evidence packs

## B) Graph traversal is one-directional and file-granular

- Expansion follows only outgoing imports (`A -> deps`)
- Caller context (`who imports/calls A`) is not included
- File-level traversal can over-pull unrelated code

Result:

- Missed integration context
- Token budget wasted on broad dependency files

## C) Feature proposal context is still coarse

- Prompt includes paths/headings/routes/entrypoints but not explicit symbol inventories
- Seed-path quality is sensitive to sparse README or weak route coverage

Result:

- Variable seed quality, especially in utility-heavy codebases

## D) Citation resolver does format resolution, not evidence validation

- Resolver correctly converts `[path:start-end]` strings to links
- It does not verify that cited spans came from retrieved/analyzed evidence

Result:

- Plausible but invalid citations can appear trustworthy

## E) A few documentation statements need correction/clarification

1. **“Cache embeddings” wording appears in README**, but the current pipeline does not create embeddings.
2. **UI location text in README may drift** as frontend layout evolves (e.g., Q&A location changed recently).
3. Some long bullets in README mix operational and retrieval concerns, reducing clarity.

---

## Recommended improvements that are worth mentioning

These are ranked by impact-to-complexity.

## Tier 1 — Immediate, low-risk, high ROI

1. **Reverse-edge graph expansion**
   - Add `imported_by` adjacency and include caller-side neighbors with caps
   - Why worth it: major relevance gains with small implementation change

2. **Strict seed-path validation**
   - Drop invalid seed paths before evidence collection
   - Why worth it: prevents thin/empty evidence caused by hallucinated paths

3. **Strict citation validation pass**
   - Verify citation path + line span against known chunk index before linkifying
   - Why worth it: materially improves trust with limited complexity

4. **Feature proposal context enrichment with symbols**
   - Add top-level symbol names per file to proposal prompt
   - Why worth it: better seed quality for little token cost

## Tier 2 — Medium effort, major quality gain

5. **Python AST-based chunking**
   - Use AST node spans for function/class-level chunking
   - Keep current window chunking as fallback on parse failure

6. **Tree-sitter chunking for JS/TS (+ select languages)**
   - Use parser nodes for semantic chunk boundaries
   - Keep regex/window fallback for unsupported edge cases

7. **Two-phase evidence budgeting**
   - Reserve chunk budget slices by source (seed/graph/search) rather than first-come truncation
   - Why worth it: avoids one source dominating evidence pack quality

## Tier 3 — Advanced options (only when justified)

8. **Symbol-aware graph (incremental call graph)**
   - Move from file-level to symbol-level traversal where possible
   - Higher precision, higher maintenance

9. **Hybrid retrieval (BM25 + embedding rerank)**
   - Keep BM25 retrieval; rerank top candidates semantically
   - Better semantic recall without immediate full vector-stack commitment

10. **Graph-RAG architecture**

  - Combine graph traversal with embedding retrieval over node/chunk representations
  - Powerful but operationally heavy; only justify for large/polyglot repos and stricter quality targets

---

## Alternate approaches (and when they make sense)

## Approach A — Keep current baseline

Use when:

- Fast iteration and low ops complexity are top priorities
- Typical repos are small/medium
- Current quality is acceptable

## Approach B — Parsing-first retrieval quality (recommended next step)

- AST/tree-sitter chunking
- Reverse-edge + bounded dual-direction traversal
- Strict citation/seed validation

Use when:

- You want better citation relevance and fewer hallucinated references
- You want quality gains without standing up vector infra

## Approach C — Semantic-heavy retrieval stack

- Embeddings + rerank + graph-enhanced retrieval
- Optional symbol graph and graph-RAG

Use when:

- Corpus scale and heterogeneity make lexical-only retrieval insufficient
- You can absorb additional infra, latency, and maintenance cost

---

## Suggested phased roadmap

## Phase 1 (short)

- Reverse-edge expansion
- Seed validation
- Citation validation
- Symbol names in proposal context

## Phase 2 (medium)

- Python AST chunking + fallback
- Evidence budget allocation by source
- Add benchmark harness for quality/regression tracking

## Phase 3 (long)

- Tree-sitter rollout for JS/TS and selected languages
- Optional hybrid rerank (BM25 + embeddings)
- Reassess need for symbol graph / graph-RAG

---

## How to evaluate if improvements are actually better

Track these metrics on a fixed benchmark repo set:

- Citation validity rate
- Citation usefulness (manual rubric)
- Evidence relevance precision@k
- Feature-page factual error rate
- Tokens per feature page
- End-to-end latency
- Failure rate (parse/retrieval errors)

Only adopt changes that improve quality materially without unacceptable cost/latency regression.

---

## Recommended doc split

- **README.md**: concise summary + links
- **guide.md**: current runtime behavior/spec
- **pipeline-improvements.md** (this file): architecture rationale, audit, alternatives, and roadmap

This keeps user-facing docs readable while preserving the engineering decision record.
