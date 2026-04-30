# Split-Workflow Migration: Portal & Testgen as Independent Pipelines

> **Status:** prototype landed in `.github/workflows/portal.yml`,
> `.github/workflows/testgen.yml`, and `scripts/testgen/fetch_via_api.py`.
> This document is the spec to feed into Copilot for hardening, retargeting
> filters, and promoting the prototype to production.

---

## 1. Why we're splitting

The current `deploy-swagger-hub.yml` runs both the Swagger UI portal build
and the AI test-case generation in **one workflow with five jobs**. That
shape was fine for the 5-spec demo but has structural problems at the real
scale (~233 active specs inside a 440 MB / 29k-file monorepo):

| Concern | Single workflow today | Split workflows |
|---|---|---|
| Portal SLA | Coupled to AI flow (parallel job, but shared build job) | Pure portal: edit → published in <60s, AI-free |
| Failure isolation | Mixed concerns, awkward "re-run failed job" | Re-run portal or testgen independently |
| Permissions surface | Both jobs inherit `pages:write`, `id-token:write`, `models:read` | Each workflow carries only what it needs |
| Cadence | Both pinned to hourly | Portal hourly; testgen daily / on-demand |
| Concurrency | `concurrency: pages` serializes both unnecessarily | Portal serialized, testgen independent |
| Adding lint / breaking-change / SDK-gen pipelines | Each becomes another job in a growing monolith | Each is a peer workflow file |
| Repo download cost | Full clone of openapi-specs (~440 MB) | Sparse-checkout for portal; Tree API for testgen |

The two pipelines have different SLAs, failure modes, permission needs, and
cadences. They should be peer workflows.

---

## 2. Architecture overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│                       openapi-specs repo (truth)                          │
│  Monorepo: ~440 MB / 29k files. ~233 ACTIVE OpenAPI YAMLs in services/    │
└──────────────────┬──────────────────────────────────┬─────────────────────┘
                   │                                  │
       sparse-checkout (active specs)        GitHub Tree+Blobs API
       ~31 MB transfer, ~10s                 1 list call + N raw fetches
                   │                                  │
                   ▼                                  ▼
   ┌──────────────────────────────┐      ┌──────────────────────────────┐
   │       portal.yml             │      │       testgen.yml            │
   │ ────────────────────────     │      │ ────────────────────────     │
   │ detect-changes → build →     │      │ fetch_via_api.py             │
   │   deploy → record            │      │   (Tree API + selective      │
   │ Pages publish (full)         │      │    blob fetch)               │
   │                              │      │ run_generation.py            │
   │ Output: Swagger UI on Pages  │      │   (AI provider, mock or      │
   │   site permanent until next  │      │    github-models)            │
   │   deploy                     │      │ Output: api-testcases        │
   │                              │      │   artifact, 30-day retention │
   └──────────────────────────────┘      └──────────────────────────────┘
              │                                  │
              ▼                                  ▼
       .deployed cache                    testgen-registry-* cache
       (SHA marker, written by            (per-spec last_blob_sha +
        portal only)                       last_processed_hash, written
                                           by testgen only)
```

Key invariants:

- **Single writer per cache entry.** `.deployed` is owned by portal.yml.
  `testgen-registry-*` is owned by testgen.yml.
- **No artifact handoff between workflows.** Each fetches its inputs
  independently from `openapi-specs` via the appropriate API.
- **The diff is physical.** In testgen, the staged spec directory IS the
  set to process — there is no sidecar "what's changed" file. The presence
  of a YAML on disk after `fetch_via_api.py` runs means it's new or changed.
- **Hash-based change detection.** Git blob SHAs are used to decide whether
  to fetch (cheap; obtained from Tree API without downloading content).
  SHA-256 of file content is used to decide whether to regenerate (existing
  testgen logic, unchanged).

---

## 3. portal.yml — Build and deploy the Swagger UI portal

### 3.1 Trigger
- Hourly schedule (`cron: 0 * * * *`)
- `workflow_dispatch` for manual runs

### 3.2 Concurrency
`concurrency: pages, cancel-in-progress: false` — Pages publishes are
serialized; we never cancel an in-flight deploy.

### 3.3 Jobs

| Job | Purpose | Notable steps |
|---|---|---|
| `detect-changes` | Decide whether anything moved upstream | Resolve openapi-specs HEAD via API; compare to `.deployed` cache; output `should_deploy=true/false` |
| `build` | Construct the static site | **Sparse-checkout active specs only**; copy Swagger UI assets; run `gen_initializer.js`; run `build_manifest.py`; upload Pages artifact |
| `deploy` | Atomic Pages publish | `actions/deploy-pages@v4` |
| `record` | Mark this SHA as deployed | Writes `.deployed` cache so future no-op runs short-circuit |

### 3.4 Sparse-checkout configuration

```yaml
- uses: actions/checkout@v4
  with:
    repository: y-didenko/openapi-specs
    ref: ${{ needs.detect-changes.outputs.specs_sha }}
    path: _specs
    token: ${{ secrets.GH_PAT || github.token }}
    fetch-depth: 1
    filter: blob:none
    sparse-checkout-cone-mode: false
    sparse-checkout: |
      services/**/*-v[0-9]*-oas.yaml
      services/**/*-v[0-9]*-oas.json
      !**/_legacy/**
      !**/deprecated/**
```

**Customize the patterns** to your real monorepo conventions before
promoting off prototype. Negative patterns (leading `!`) exclude. The
prototype assumes the same `services/<id>/<id>-v<N>-oas.{yaml,json}`
naming used in the demo data.

### 3.5 Behaviour at scale

- **Spec corpus copied to dist/specs:** ~31 MB
- **Pages artifact upload:** ~36 MB (specs + Swagger UI assets), ~30s
- **Pages site size:** well under the 1 GB limit
- **End-to-end portal run with changes:** ~60–90s
- **End-to-end portal run with no changes:** ~5s (short-circuited at
  detect-changes)

---

## 4. testgen.yml — Fetch only changed specs and generate test cases

### 4.1 Trigger
- Daily schedule (`cron: 0 3 * * *`) — tune to AI-cost vs freshness
- `workflow_dispatch` with inputs `ai_provider`, `force_regenerate`

### 4.2 Concurrency
`concurrency: testgen, cancel-in-progress: false` — never cancel an
in-flight AI generation; let it complete and start the next on next trigger.

### 4.3 Single job: `generate`

Steps:

1. **Checkout swagger-hub** (scripts only — no openapi-specs clone)
2. **Restore registry cache** (`testgen-registry-*` with `restore-keys`)
3. **`fetch_via_api.py`**:
   - GET `openapi-specs` HEAD SHA via Commits API (1 call)
   - GET recursive Tree at that SHA (1 call, returns up to 100k entries
     with `{path, sha, size, type}`)
   - Filter tree to candidate spec paths (`SPEC_PATH_RE`)
   - Apply `is_retired()` predicate to drop legacy/deprecated
   - For each remaining entry: compare git blob SHA to
     `registry.specs[id].last_blob_sha`. If equal, skip. Otherwise fetch
     the raw blob via the Git Blobs API.
   - Write fetched content to `data/fetched/<source_path>`
   - Build a **lean manifest** (`data/manifests/openapi-manifest.json`)
     containing only the fetched entries
   - Update registry's `last_blob_sha` for each fetched spec
4. **`run_generation.py`** (existing, unchanged):
   - Iterates the lean manifest
   - Internally classifies via `detect_changed_specs.py` against
     `last_processed_hash` (SHA-256 — independent of blob SHA)
   - Calls AI provider, renders markdown, updates registry's
     `last_processed_hash` on success via the now-merge-friendly
     `update_registry()`
5. **Save registry cache**
6. **Upload `api-testcases` artifact** (30-day retention)

### 4.4 Why two hash fields in the registry

| Field | Computed from | Used by | Purpose |
|---|---|---|---|
| `last_blob_sha` | Git's blob SHA-1, returned by Tree API | `fetch_via_api.py` | Decide whether to **download** the file. Free from the Tree API — no content needed. |
| `last_processed_hash` | SHA-256 of file content | `run_generation.py` (via `detect_changed_specs.py`) | Decide whether to **regenerate** the test cases. Survives format-only changes consistently. |

These are two independent decisions:

- A spec content change → blob SHA differs → download → SHA-256 differs →
  regenerate. ✅
- A no-op commit on openapi-specs → blob SHA unchanged → no download →
  no regeneration. ✅
- (Edge case) A blob with whitespace-only YAML reformat → blob SHA differs
  (any byte change) → download → SHA-256 differs (any byte change) →
  regenerate. We accept this; could be sharpened by canonicalizing YAML
  before hashing, but not in scope for the prototype.

### 4.5 Behaviour at scale

- **Tree API call:** 1 request, ~1s, returns ~233 active spec entries from
  among 29k files
- **Typical run (0–5 changed specs):** 1 + 5 API calls, ~3s of network
- **Total runtime including AI mock:** ~10–20s
- **Total runtime with `github-models` provider:** dominated by AI
  latency, not the fetch step
- **First run on empty registry:** fetches all ~233 active specs
  (~30s of API calls), then full generation

---

## 5. Files in this prototype

| File | New / Modified | Description |
|---|---|---|
| `.github/workflows/portal.yml` | new | Sparse-checkout portal workflow |
| `.github/workflows/testgen.yml` | new | Tree-API testgen workflow |
| `.github/workflows/deploy-swagger-hub.yml` | **left in place** | Old monolith. Delete or disable after A/B verification. |
| `scripts/testgen/fetch_via_api.py` | new | Tree+Blobs API client; decides what to fetch by `last_blob_sha`; writes lean manifest |
| `scripts/testgen/update_registry.py` | modified | Now merges into existing entries instead of replacing them, so `last_blob_sha` survives the post-generation update from `run_generation.py` |
| `scripts/testgen/run_generation.py` | unchanged | Continues to operate on a manifest + specs-dir; doesn't know or care that the input is now lean |
| `scripts/testgen/detect_changed_specs.py` | unchanged | Continues using SHA-256 for the regeneration decision |
| `scripts/swagger/build_manifest.py` | unchanged | Still used by portal.yml from a sparse-checkout dir |

---

## 6. Customization checklist for Copilot

Search-tags I left in the code so the next pass is mechanical:

- **`# CUSTOMIZE`** in `scripts/testgen/fetch_via_api.py`:
  - `SPEC_PATH_RE` — adjust the regex to your real spec path convention
  - `is_retired(path)` — implement the active/retired filter that matches
    your monorepo convention (path component, filename infix, sidecar
    file, OpenAPI extension, etc.)
- **`# PROTOTYPE FILTER`** in `.github/workflows/portal.yml`:
  - `sparse-checkout` patterns — same logical filter as `is_retired`,
    expressed as gitignore-style negative patterns

The two filters should be **kept in sync semantically**. The most robust
way is to derive both from a single source — for example, a YAML config
file checked into swagger-hub (`config/spec-filters.yml`) that both the
sparse-checkout step and `fetch_via_api.py` read. Out of scope for the
prototype but worth proposing if the filter logic becomes non-trivial.

---

## 7. Known gaps / production hardening list

These are intentionally out of scope for the prototype but should be
handled before promoting:

1. **Failure-recovery for testgen.** `fetch_via_api.py` writes
   `last_blob_sha` *immediately* after fetching. If AI generation later
   fails on that spec, the next run won't retry it until the spec content
   actually changes. To make this transactional, move the
   `last_blob_sha` write into `update_registry()` post-success and
   guard with `if status == "success"`.

2. **Classification labels are slightly off.** Specs newly created by the
   fetcher are reported as `changed` (not `new`) by `run_generation.py`,
   because the fetcher pre-creates a stub registry entry with
   `last_blob_sha` but no `last_processed_hash`. Functionally correct;
   cosmetic in reports. One-line fix in `detect_changed_specs.py`:

   ```python
   if sid not in reg_specs or "last_processed_hash" not in reg_specs[sid]:
       new_specs.append(entry)
   ```

3. **Tree truncation.** GitHub's recursive-tree API tops out at 100k
   entries / ~7 MB of response. At 29k files the prototype has plenty
   of headroom; the script warns if it ever truncates. For >100k repos
   we'd need to walk subtrees manually.

4. **Registry pruning is enabled.** `fetch_via_api.py` removes registry
   entries for service IDs that no longer appear in the active set.
   This means: if you accidentally exclude active specs (e.g. via a
   too-broad `is_retired`), they'll lose their history on the next run.
   Consider adding a `--no-prune` flag for safety during filter
   transitions.

5. **Old monolith still active.** `.github/workflows/deploy-swagger-hub.yml`
   continues to run on its hourly schedule alongside the new workflows.
   To avoid double-publishing to Pages, either delete the old file or
   remove its `schedule:` trigger before enabling `portal.yml`.

6. **Filter convention coupling.** The sparse-checkout patterns in
   `portal.yml` and `is_retired()` in `fetch_via_api.py` express the
   same business rule in two languages. Consider unifying via a config
   file (see Customization checklist).

7. **Swagger UI dropdown UX.** With 233 specs the dropdown is workable.
   At 1000+ it becomes a navigation problem — categorization, search,
   or a custom landing page should be planned.

8. **Concurrent failure visibility.** When testgen fails on a real AI
   provider (rate limits, model errors), no one is notified today.
   Consider adding a final "post status" step that opens an issue or
   pings a webhook on failure.

---

## 8. Migration plan

A safe path from current state to the split workflows:

1. **Land the prototype.** This commit. Old workflow stays active.
2. **Customize filters.** Adjust `SPEC_PATH_RE`, `is_retired()`, and
   `sparse-checkout` patterns to the real monorepo conventions.
3. **Manual smoke test on testgen.yml.** Trigger via `workflow_dispatch`
   with `ai_provider: mock`. Confirm:
   - Tree API call succeeds
   - Active specs filtered correctly (compare count vs known reality)
   - Registry cache restores and persists
   - Generated test-cases artifact uploaded
4. **Manual smoke test on portal.yml.** Trigger via `workflow_dispatch`.
   Confirm:
   - Sparse-checkout pulls only spec files (verify `_specs/` size)
   - Pages site builds and deploys correctly
   - Spec count on the rendered portal matches reality
5. **Disable old monolith.** Either delete
   `.github/workflows/deploy-swagger-hub.yml` or remove its `schedule:`
   trigger so it only runs on manual dispatch as a fallback.
6. **Enable schedules on the new workflows.** They're already wired in
   the prototype.
7. **Observe for a week.** Verify cache hit rates, fetch counts, AI
   spend (if not on mock).
8. **Remove old monolith entirely** once confidence is established.

Each step is independently revertible. The prototype is designed to
coexist with the existing workflow until you're ready to switch.
