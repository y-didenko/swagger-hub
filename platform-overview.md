# API Quality Platform — Overview & Architecture

> **Purpose of this document**
> Single comprehensive context for the API Quality Platform — what it is, why it
> exists, how it's architected, what's built, what's planned, and which decisions
> have already been made. Designed to be fed into a coding assistant (Copilot,
> Claude, etc.) so future work has the full picture without rediscovery cost.
>
> Companion docs:
> - `generation-spec.md` — original AI generation spec
> - `split-workflows-spec.md` — split-workflow migration spec (deeper detail on the pipeline split)
> - `api-quality-platform-deck.md` — leadership presentation (vision-level summary)
> - `README.md` — usage / how-to-run

---

## TL;DR

- Platform consumes an OpenAPI-specs monorepo and produces **two independent outputs**: a unified Swagger UI portal and AI-generated test-design artifacts.
- The two outputs run as **two fully independent pipelines** sharing only the source repo. No common infrastructure by default; an optional shared layer (notifications, dashboards) is anticipated long-term but not built.
- Today's runtime is **GitHub Actions + GitHub Models**. No external infra to operate.
- MVP is **proven**: portal is live with 200+ specs and a categorized search picker; AI engine produces sample test cases + spec quality reviews on a mock provider, real provider switchable.
- The roadmap has three horizons: **Now (MVP)** → **Next 1–2 quarters** (full rollout, real AI, Confluence, notifications, version history) → **Long-term 6–12 mo** (BRDs/ACs, Postman/Bruno/Java, dashboards, Azure DevOps).

---

## Problem statement

A monorepo with hundreds of OpenAPI specs (~233 active out of ~532 spec files within a 440 MB / 29k-file corporate monorepo). Three problems compound:

1. **API discovery is fragmented.** Specs are scattered across services. Engineers can't easily find what already exists; onboarding is slow; cross-team integration is harder than it should be.
2. **Test design is manual and slow.** Writing test cases per service takes days of human effort. The org has more APIs than QA capacity.
3. **Spec quality varies wildly.** Inconsistencies, missing examples, ambiguous schemas — issues surface late, usually in integration testing.

The platform addresses all three: portal solves discovery; AI engine produces test cases at scale; spec quality review surfaces problems at commit time, not integration time.

---

## Architectural decisions (already settled)

These were debated and resolved. Don't relitigate without strong cause.

### Q1 — Spec quality review and test-case generation are sibling features

They're conceptually two products with two consumers:
- **Spec QA** → consumed by spec authors / API designers ("your spec is missing X")
- **Test cases** → consumed by QA engineers ("here are scenarios to validate")

Today they may share an AI call (one prompt produces both outputs in one MD), but they evolve as independent features. Keep prompts/outputs/dashboards separable.

### Q2 — Portal and AI Engine are fully independent pipelines

No shared infrastructure by default. Different triggers, different cadences, different failure modes, different audiences. The cost of "duplication" (each pipeline does its own change detection, fetch, state management) is real but small (~3–10s per pipeline run) and worth it for independence.

**An optional shared layer** is anticipated for long-term cross-cutting concerns (notifications hub, observability, common AI provider abstraction). Don't build it yet. Define explicit triggers for when shared infra would be required: e.g., when both pipelines need the same notification target with the same delivery semantics.

### Q3 — Business requirements (BRDs / ACs / AVTs) are deferred

Different shape from OpenAPI specs (free-form documents vs structured contracts), different consumers, governance complications. Treat as a separate future capability, not "another input source". Out of scope for current implementation.

### Q4 — Quality dashboards are long-term outline only

We don't have enough usage data to design metrics meaningfully. Candidates to consider when we do: spec quality score, test coverage %, generation success rate, adoption (% teams using artifacts). Pick 1–2 once usage data exists.

### Q5 — MVP scope

Done when the following all work end-to-end:
- Portal deployed with categorization + search across all active specs
- Test case generation proven on sample APIs (MD artifacts)
- Spec quality review proven on sample APIs (MD artifacts)
- Change detection + per-pipeline state tracking

After MVP, expand toward:
- Full-scale AI generation across the corpus
- Version history of generated artifacts

---

## Layered architecture

Eight layers describe both pipelines. L1 and L7 are bookends (shared); L2–L6 run as parallel columns per pipeline; L8 is cross-cutting and only present in the long-term version.

| Layer | Purpose | Shared / per-pipeline |
|---|---|---|
| L1 — Sources | Raw inputs the system reads | Shared |
| L2 — Triggers | What initiates a pipeline run | Per-pipeline |
| L3 — Pipeline core | Detect → fetch → process | Per-pipeline |
| L4 — State | Persistent memory across runs | Per-pipeline |
| L5 — Output | Artifacts produced | Per-pipeline |
| L6 — Distribution | Where artifacts land | Per-pipeline (some shared channels long-term) |
| L7 — Consumers | Who reads / uses outputs | Shared audience |
| L8 — Observability | Cross-cutting metrics, audit, cost | Shared (long-term only) |

### Version 1 — Current / Short-term

```
┌─────────────────────────────────────────────────────────────────────────┐
│  L1  SOURCES                                                            │
│      • openapi-specs repo                                               │
└─────────────────────────────────────────────────────────────────────────┘
                       │                              │
            ┌──────────▼──────────┐         ┌─────────▼─────────────┐
            │  PORTAL pipeline    │         │   AI ENGINE pipeline  │
            │                     │         │                       │
            │  L2 Triggers        │         │  L2 Triggers          │
            │  • hourly cron      │         │  • daily cron         │
            │  • manual dispatch  │         │  • manual dispatch    │
            │                     │         │                       │
            │  L3 Pipeline        │         │  L3 Pipeline          │
            │  • SHA-level detect │         │  • blob-SHA detect    │
            │  • sparse-checkout  │         │  • Tree-API selective │
            │    (~31 MB)         │         │    fetch              │
            │  • build SUI bundle │         │  • AI prompts:        │
            │  • inject picker    │         │    QA + test cases    │
            │                     │         │  • MD render          │
            │                     │         │                       │
            │  L4 State           │         │  L4 State             │
            │  • .deployed cache  │         │  • registry cache     │
            │    (last SHA)       │         │    (per-spec hashes)  │
            │                     │         │                       │
            │  L5 Output          │         │  L5 Output            │
            │  • static SUI site  │         │  • MD test-case packs │
            │  • manifest.json    │         │  • MD spec QA notes   │
            │                     │         │                       │
            │  L6 Distribution    │         │  L6 Distribution      │
            │  • GitHub Pages     │         │  • GitHub Artifacts   │
            └──────────┬──────────┘         └──────────┬────────────┘
                       │                              │
┌──────────────────────▼──────────────────────────────▼───────────────────┐
│  L7  CONSUMERS                                                          │
│      • Engineers / QA browsing the portal                               │
│      • QA reading generated MD artifacts (via Actions UI)               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Version 2 — Long-term

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  L1  SOURCES                                                                        │
│      • openapi-specs repo  •  BRD / ACs / AVTs (new)  •  prior spec versions        │
└─────────────────────────────────────────────────────────────────────────────────────┘
                       │                                     │
            ┌──────────▼─────────────┐         ┌─────────────▼─────────────────────┐
            │  PORTAL pipeline       │         │   AI ENGINE pipeline              │
            │                        │         │                                   │
            │ L2 Triggers            │         │ L2 Triggers                       │
            │ • cron + manual        │         │ • cron + manual                   │
            │ • PR webhook           │         │ • PR webhook                      │
            │ • on-demand from UI    │         │ • on-demand from portal           │
            │                        │         │                                   │
            │ L3 Pipeline            │         │ L3 Pipeline                       │
            │ • detect + fetch       │         │ • detect + selective fetch        │
            │ • build SUI            │         │ • prompt management (versioned)   │
            │ • polished UX          │         │ • AI provider abstraction:        │
            │ • embedded analytics   │         │   GH Models / corp AI / fallback  │
            │                        │         │ • two siblings, separate prompts: │
            │                        │         │   ├─ Spec quality review          │
            │                        │         │   └─ Test case generation         │
            │                        │         │ • multi-format output stage:      │
            │                        │         │   MD / Postman / Bruno / Java /   │
            │                        │         │   Azure DevOps test cases         │
            │                        │         │                                   │
            │ L4 State               │         │ L4 State                          │
            │ • .deployed cache      │         │ • registry (with version history) │
            │ • analytics store      │         │ • prompt version log              │
            │                        │         │ • quality scoring history         │
            │                        │         │                                   │
            │ L5 Output              │         │ L5 Output                         │
            │ • static SUI site      │         │ • MD test-case packs              │
            │ • analytics events     │         │ • MD spec QA notes                │
            │                        │         │ • Postman / Bruno collections     │
            │                        │         │ • Java auto-tests                 │
            │                        │         │ • Azure DevOps test-case payloads │
            │                        │         │                                   │
            │ L6 Distribution        │         │ L6 Distribution                   │
            │ • GitHub Pages         │         │ • GitHub Artifacts                │
            │ • analytics dashboard  │         │ • Confluence pages (auto-sync)    │
            │                        │         │ • Postman/Bruno workspace push    │
            │                        │         │ • Java test repo PRs              │
            │                        │         │ • Azure DevOps API push           │
            │                        │         │ • Notifications: Teams / DMs      │
            └──────────┬─────────────┘         └─────────────┬─────────────────────┘
                       │                                     │
            ┌──────────▼─────────────────────────────────────▼─────────────────────┐
            │  L8 OBSERVABILITY (cross-cutting, the optional shared layer)          │
            │      • Quality dashboards: spec scores, coverage, success rate        │
            │      • Audit log of generations / deployments                         │
            │      • Cost tracking per pipeline                                     │
            │      • Notifications hub (single place; both pipelines feed it)       │
            └──────────────────────────────┬────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼───────────────────────────────────────┐
│  L7  CONSUMERS                                                                    │
│      • Engineers / QA via portal                                                  │
│      • QA via Confluence test plans                                               │
│      • Test automation engineers via Postman/Bruno                                │
│      • Test management via Azure DevOps integration                               │
│      • Spec authors notified of QA findings                                       │
│      • Eng leadership via quality dashboards                                      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Layer evolution V1 → V2

| Layer | V1 (today) | V2 (long-term) |
|---|---|---|
| L1 Sources | One: openapi-specs | + BRDs/ACs (separate capability), historical specs |
| L2 Triggers | Cron + manual | + PR webhook, on-demand from portal UI |
| L3 Pipeline | Single bundled AI prompt; one provider | Separate prompts per sibling; provider abstraction; multi-format output stage |
| L4 State | Cache + registry | + version history, prompt log, scoring history |
| L5 Output | MD only | + Postman, Bruno, Java tests, Azure DevOps payloads |
| L6 Distribution | Pages + Artifacts | + Confluence, Postman/Bruno workspace, Java repo PRs, Azure DevOps push, Teams notifications |
| L7 Consumers | Portal users + QA via Actions | + spec authors, automation engineers, test management, eng leadership |
| L8 Observability | (not present) | New cross-cutting layer |

---

## The two pipelines, in detail

### Portal pipeline

**Purpose:** read-only consumption surface. Aggregate active OpenAPI specs into one searchable Swagger UI on GitHub Pages.

**Trigger model:**
- Hourly schedule (`cron: 0 * * * *`)
- `workflow_dispatch` (manual)
- Future: PR webhook on openapi-specs to deploy near-real-time

**Internal flow:**
1. **Detect** — fetch openapi-specs HEAD SHA. Compare against `.deployed` cache. Skip pipeline if SHA matches (no-op short-circuit, ~5s total run).
2. **Fetch** — `actions/checkout` with `sparse-checkout` filtering to active spec paths only. Pulls ~31 MB instead of 440 MB.
3. **Build** — copy swagger-ui-dist assets, copy specs into `dist/specs/`, generate the categorized search picker via `gen_initializer.py`.
4. **Upload Pages artifact** — full bundle (~36 MB) to `actions/upload-pages-artifact`.
5. **Deploy** — `actions/deploy-pages` does atomic Pages publish.
6. **Record** — write the new SHA to `.deployed` cache.

**State:** `.deployed` Actions cache, keyed by SHA. Just a marker — no per-spec data needed because Pages publishes a full snapshot every time anyway.

**Output:** static Swagger UI site with categorized search across all active specs.

**Distribution:** GitHub Pages (`y-didenko.github.io/swagger-hub/`).

**Code locations:**
- `.github/workflows/portal.yml` — workflow (prototype, manual trigger)
- `.github/workflows/deploy-swagger-hub.yml` — deprecated monolith (active, manual fallback)
- `scripts/gen_initializer.py` — picker bar + Swagger UI bootstrap; reads `config/spec-categories.yml`
- `scripts/swagger/build_manifest.py` — produces `data/manifests/openapi-manifest.json` from staged specs
- `scripts/swagger/validate_specs.py` — parseability check
- `scripts/common/` — shared utilities (hashing, IO, OpenAPI parsing)
- `config/spec-categories.yml` — category taxonomy

### AI Engine pipeline

**Purpose:** generation surface. Produce AI-driven test-design artifacts and spec quality reviews per service.

**Trigger model:**
- Daily schedule (`cron: 0 3 * * *`) — tune to AI cost / freshness trade-off
- `workflow_dispatch` (manual) with inputs `ai_provider` (mock | github-models) and `force_regenerate` (true | false)

**Internal flow:**
1. **Resolve HEAD SHA** of openapi-specs via Commits API (1 call).
2. **List recursive tree** at HEAD via Tree API (1 call returns up to 100k path + git blob SHA entries).
3. **Filter** to candidate spec paths matching `SPEC_PATH_RE`, exclude retired via `is_retired(path)`.
4. **Compare blob SHAs** against the registry's `last_blob_sha` per service. Specs with unchanged blob SHAs are skipped (no download).
5. **Fetch only changed specs** via the Git Blobs API (raw content per blob SHA).
6. **Process each fetched spec**:
   - `prepare_ai_input.py` — extract a compact, AI-friendly representation of the spec.
   - Render system prompt (`prompts/system/api-testcases-system.md`) and user template (`prompts/templates/api-testcases-user.md`).
   - Call AI provider — `MockProvider` or `GithubModelsProvider`.
   - Parse JSON response, render to markdown via `render_markdown.py`.
7. **Update registry**:
   - `last_blob_sha` written by `fetch_via_api.py` immediately after fetch.
   - `last_processed_hash` (SHA-256 of content) + `status` + `output_file` written by `update_registry.py` after generation succeeds.
   - **Merge semantics**: `update_registry.py` merges into existing entries rather than overwriting, so `last_blob_sha` survives the post-generation update.
8. **Save registry** to Actions cache.
9. **Upload `api-testcases` artifact** (30-day retention).

**State:**
- `data/registry/processed-specs.json` — per-spec record:
  ```json
  {
    "specs": {
      "<service_id>": {
        "service_id": "users",
        "source_path": "services/users/users-v1-oas.yaml",
        "last_blob_sha": "d68b8992c13eaf04eb214d52c2a05740955a14fd",
        "last_fetched_at": "2026-04-30T20:17:19Z",
        "last_processed_hash": "e54d3f2c582c1b228c11c7b00b1ca97be3833da5d...",
        "last_processed_at": "2026-04-30T20:21:19Z",
        "output_file": "testcases/users-testcases.md",
        "output_hash": "...",
        "status": "success",
        "notes": "",
        "confluence_page_id": null,
        "confluence_synced_at": null
      }
    }
  }
  ```
- Persisted via Actions cache with key `testgen-registry-${{ github.run_number }}` and `restore-keys: testgen-registry-` for fallback.

**Output:** Markdown test-case packs + spec QA reviews per service.

**Distribution:** GitHub Artifacts (today). Future: Confluence pages, Teams notifications.

**Code locations:**
- `.github/workflows/testgen.yml` — workflow (prototype, manual trigger)
- `scripts/testgen/fetch_via_api.py` — Tree-API selective fetcher (decides what to download)
- `scripts/testgen/run_generation.py` — orchestrator (calls AI, renders MD, updates registry)
- `scripts/testgen/detect_changed_specs.py` — classifies new/changed/unchanged via SHA-256
- `scripts/testgen/prepare_ai_input.py` — extracts AI-friendly spec representation
- `scripts/testgen/render_markdown.py` — renders AI JSON output → MD
- `scripts/testgen/update_registry.py` — merges generation result into registry (preserves `last_blob_sha`)
- `prompts/system/api-testcases-system.md` — system prompt
- `prompts/templates/api-testcases-user.md` — user prompt template
- `prompts/templates/spec-gap-policy.md` — policy for reporting spec gaps

### Sibling features within AI Engine

Today bundled into one AI call. Long-term may split.

**Spec quality review:**
- Audience: spec authors / API designers
- Output: list of issues, recommendations, gaps
- Trigger: spec change → review
- Lifecycle: regenerated whenever the spec changes

**Test case generation:**
- Audience: QA engineers
- Output: test cases (positive, negative, edge), validation points, priority
- Trigger: spec change → regenerate
- Lifecycle: same as spec quality

Decision deferred: do we split into two prompts/calls/outputs (better separation, double the cost), or keep one bundled call (cheaper, but harder to evolve independently)?

---

## Current state — what's built

**Portal** (live):
- Live at `https://y-didenko.github.io/swagger-hub/`
- 221 OpenAPI specs aggregated (216 generated for volume testing + 5 hand-written)
- 22 categories with cross-listing (4 specs cross-listed: users, accounts, audit, segments)
- 2 specs deliberately uncategorized to demonstrate the "Other" bucket
- Native HTML picker: `<select>` with `<optgroup>` (browse by category) + `<input list>` with `<datalist>` (search-as-you-type)
- Native Swagger UI `DarkModeToggle` preserved via click-forwarding proxy pattern (see Lessons Learned)

**AI Engine** (prototype):
- `testgen.yml` workflow in place, manual trigger only (dormant on schedule)
- `fetch_via_api.py` smoke-tested against the live openapi-specs repo: full first-run fetched 221 specs; second run skipped all (zero changes); update-then-rerun correctly fetched only changed specs
- Mock provider produces deterministic placeholder MD artifacts (1 test case per spec)
- Real `github-models` provider switchable via env var or workflow input
- Registry preserves both `last_blob_sha` (set by fetch) and `last_processed_hash` (set by run_generation) thanks to merge-style `update_registry.py`

**Workflow status:**
- `.github/workflows/deploy-swagger-hub.yml` — `[DEPRECATED]`, manual trigger only (was the original monolith)
- `.github/workflows/portal.yml` — `[PROTOTYPE]`, manual trigger only
- `.github/workflows/testgen.yml` — `[PROTOTYPE]`, manual trigger only

No scheduled runs are firing yet. The user wants the prototypes dormant until filters are retargeted to the real corporate openapi-specs layout.

---

## Roadmap

### Now / Proven (MVP)

- ◆ Portal deployed, 221+ specs aggregated, categorized search working
- ◆ Test-case generation proven on sample APIs (markdown artifacts)
- ◆ Spec quality review proven on sample APIs (markdown artifacts, currently bundled with test cases)
- ◆ Change detection working: portal SHA-level, AI engine git-blob-SHA level
- ◆ Registry tracks processed specs across runs (Actions cache + restore-keys)

### Next 1–2 quarters

- Retarget filters (`SPEC_PATH_RE`, `is_retired()`, sparse-checkout patterns) to the real corporate openapi-specs layout
- Move off mock provider — real GitHub Models in production
- Iterate prompts based on real-output review (spec quality, test cases)
- Full-scale rollout: every active spec processed
- Split spec QA and test cases into separate prompts/outputs (or commit to one bundled output if that's simpler at scale)
- Notifications: Teams channels, individual reviewers when their specs get fresh artifacts
- Confluence publishing: replace/augment MD artifacts with auto-synced Confluence pages
- Version history of generated artifacts (track what changed and when)
- Promote prototypes off `[PROTOTYPE]`: re-enable schedule triggers, retire `deploy-swagger-hub.yml`

### Long-term (6–12 months)

- BRD / acceptance-criteria as a second input source (separate capability — pitfalls TBD)
- Postman / Bruno collection generation
- Java auto-test generation
- Azure DevOps test-case integration
- Quality dashboards: spec scores, coverage %, generation success, adoption (specifics emerge once real-usage data exists)
- L8 Observability layer materializes: dashboards, audit log, cost tracking, notifications hub

### Vision items not yet sequenced

- Multi-tenant / team-scoped views (dashboards filtered by team ownership)
- Feedback loop: humans rate AI output → improves prompts
- Internal AI model integration (corp-locked, off public providers)
- API change-impact analysis (diff a new spec version vs deployed → flag breaking changes)

---

## Benefits and trade-offs

### Benefits

- **Scale without proportional headcount.** Test-design coverage for hundreds of APIs without growing the QA team by hundreds.
- **Faster spec quality feedback.** Issues surface at commit time, not in integration testing.
- **Consistent output.** Same structure of test cases / quality review across all APIs regardless of which team owns them.
- **Self-service API catalog.** Engineers find and explore APIs without DM'ing colleagues.
- **Low operational footprint.** Runs entirely on GitHub Actions + GitHub Models. No servers, no separate platform team needed.
- **Composable artifacts.** Markdown output flows into Confluence, dashboards, and (later) Postman/Bruno/Java without rework.
- **Living documentation.** Artifacts regenerate automatically when specs change.

### Trade-offs we accept

- **AI output needs human review — especially early.** Augments QA, doesn't replace it. Generated artifacts are starting points, not final deliverables.
- **AI is non-deterministic.** Same spec, slightly different output run-to-run. Acceptable for design artifacts; would be a problem for executable code.
- **Garbage in → mediocre out.** Bad specs produce thin artifacts. Spec hygiene becomes a prerequisite — that's actually good, but it shifts work earlier.
- **AI cost scales with usage.** Full rollout × real provider × hourly cadence has a real monthly bill. Cadence/scope are deliberate choices.
- **Adoption is the hard part.** Generation is technical; getting QA/dev teams to actually use the artifacts is cultural.
- **Not yet executable.** Today's output is descriptive (test design), not runnable tests. Postman/Bruno/Java generation is on the roadmap, not delivered.

---

## Open questions / decisions ahead

1. **Quality metrics — what do we score?**
   - Spec quality (completeness, examples, consistency)?
   - Test coverage (% of endpoints with generated cases)?
   - Generation success rate (% of specs processed without AI failures)?
   - Adoption (% of teams using the artifacts)?
   Each is a different dashboard. Pick once usage data exists.

2. **AI provider strategy.**
   GitHub Models works for now. Plan: a second provider for redundancy? A locked-down corporate AI? An internal model? Affects abstraction design.

3. **BRD / AC integration.**
   Different shape than specs (free-form vs structured), different consumers, governance complications. Worth a separate design discussion before committing.

4. **Cost vs cadence trade-off.**
   AI calls cost money at scale. Hourly vs daily vs on-demand affects bill and freshness. Worth a deliberate choice before full rollout.

5. **Spec QA + test cases: one prompt or two?**
   Bundled is cheaper (one AI call); split makes each output easier to evolve and easier to opt into separately. Decide before full rollout.

6. **Failure-recovery for testgen.**
   `fetch_via_api.py` writes `last_blob_sha` immediately after fetching. If AI generation fails, the next run won't retry until the spec content changes. To make this transactional, move `last_blob_sha` write into `update_registry()` post-success. Known, intentional prototype caveat.

7. **Pruning stale registry entries.**
   `fetch_via_api.py` removes registry entries for service IDs no longer in the active set. If a too-broad `is_retired()` filter accidentally excludes active specs, they lose history. Consider a `--no-prune` flag during filter transitions.

8. **The optional shared layer trigger criteria (Q2).**
   What event would force us to build common infrastructure? E.g., when both pipelines need notifications with the same delivery semantics, or when observability data must be queryable across pipelines. Define the criteria so we don't build it prematurely or too late.

---

## Technical notes / lessons learned

These are decisions and gotchas worth capturing so future work doesn't rediscover them.

### Why sparse-checkout (portal) and Tree API (AI engine)

The corporate openapi-specs monorepo is **440 MB / 29k files**, with only ~233 active spec YAMLs (~31 MB). Cloning the whole thing per workflow run is wasteful.

- **Portal** uses `actions/checkout` with `sparse-checkout: services/**/*-oas.{yaml,json}` and `filter: blob:none`. Pulls only the spec files. ~5–15s instead of 30–90s.
- **AI Engine** never clones at all. It calls the **GitHub Tree API** (1 request returns all paths + git blob SHAs at HEAD), filters in-memory, and fetches raw content via the Git Blobs API only for specs whose blob SHA differs from the registry. Typical run: 1 + N HTTP requests where N = diff size.

Pages publish itself is always a full upload — that's a Pages limitation, not ours. So Pages-side optimization isn't a thing.

### Git blob SHA vs SHA-256 in the registry

Two hash fields, two purposes:

| Field | Computed from | Used by | Purpose |
|---|---|---|---|
| `last_blob_sha` | Git blob SHA-1, returned by Tree API | `fetch_via_api.py` | Decide whether to **download**. Free from Tree API — no content needed. |
| `last_processed_hash` | SHA-256 of file content | `run_generation.py` (via `detect_changed_specs.py`) | Decide whether to **regenerate** test cases. Independent of fetch decision. |

These are separate decisions:
- Spec content change → blob SHA differs → download → SHA-256 differs → regenerate. ✓
- No-op commit → blob SHA unchanged → no download → no regeneration. ✓
- Whitespace-only YAML reformat → blob SHA differs → download → SHA-256 differs → regenerate (acceptable; could canonicalize to suppress).

### Native HTML for the picker

The categorized + searchable picker uses two native primitives:

- `<select>` with `<optgroup>` — categorized browse, native dropdown UX, free keyboard nav, accessible.
- `<input list="...">` with `<datalist>` — search-as-you-type with native filtering, native suggestion UI.

About **25 lines of glue JS** wires both to Swagger UI's spec switching API. Browser handles filtering, keyboard, mobile UX, accessibility. No framework, no bundler, no build step.

Native limitations to know:
- Datalist styling is mostly browser-controlled (you can style the input but not the suggestion popup).
- No fuzzy matching (substring/prefix only; "uesr" doesn't match "users").
- No live count badges in optgroup labels (static labels).
- "Shared" badges on cross-listed APIs need custom CSS.

These limits are acceptable for the prototype.

### Picker structure (final shape)

Two controls plus a count plus the native DarkModeToggle proxy:

```
[ Category: All categories (221) ▼ ]   [ Search 221 APIs... ]   221 APIs   💡
```

- Category dropdown filters everything (datalist contents + count).
- "All categories" mode: datalist values formatted `Spec Name — Category Name` so search matches either.
- Filtered mode: datalist values are bare spec names (category is implied).
- Picking from search switches Swagger UI to that spec.

### swagger-ui-dist DOES ship a DarkModeToggle

This took painful debugging. The `swagger-ui-dist@5.32.5` standalone preset registers a `DarkModeToggle` component in the topbar. Layout:
```
[ Logo ] → [ "Select definition" form / URL form ] → [ DarkModeToggle ]
```

The component renders `<div class="dark-mode-toggle"><button><svg/></button></div>`. Clicking toggles `dark-mode` class on `<html>`, which Swagger UI's CSS responds to.

**Initial wrong searches:** grepping for `theme`, `themeToggle`, `darkMode`, `switchTheme` returned nothing. The actual identifier is `DarkModeToggle` (specific casing). The single match for `theme` in the bundle was `syntaxHighlight.theme: "agate"` (code highlighter) — unrelated and dismissed too early.

### React 17+ event delegation breaks DOM-moves outside the React root

Initial attempt to merge the topbar with the picker: DOM-move the `.dark-mode-toggle` element out of `.swagger-ui .topbar` and into `#api-picker`. The button looked right but **clicks didn't toggle dark mode**.

Why: React 17+ uses event delegation rooted at the React mount point (`#swagger-ui`). When a click happens inside the React tree, the event bubbles up to that root, where React's listener catches it and dispatches to the right handler. **Moving the button OUT of `#swagger-ui` means clicks on it don't reach React's listener.**

**Fix: click-forwarding proxy.**
- Keep the native button **in place** inside the topbar (still in DOM, just `display: none`).
- Create a **mirrored proxy** `<div class="dark-mode-toggle">` inside the picker.
- On proxy click, programmatically call `originalButton.click()`. The dispatched click event still bubbles up the React tree (since the original button is still there), React catches it, the dark-mode toggle works.
- A `MutationObserver` mirrors the original button's `innerHTML` to the proxy whenever React swaps its lightbulb / lightbulb-off SVG (so the icon stays in sync).

Code in `scripts/gen_initializer.py` under `setupThemeProxy()`.

### Filter-based dark mode = wrong palette

Earlier attempt: `html[data-theme="dark"] #swagger-ui { filter: invert(0.92) hue-rotate(180deg); }` with counter-inverts on images/svg/code. It "works" but inverts every color including Swagger UI's brand greens/blues/oranges (the GET/POST/PUT/DELETE pill colors). Method colors carry semantic meaning; inverting them ruins it.

**Lesson:** for a docs tool with semantic colors, the filter trick is wrong. Use the framework's own theme support if it exists. Swagger UI 5.x has `.dark-mode` class on `<html>` — that's the right hook. Hand-tuned dark theme overrides would be option B (~150–250 lines of CSS); not needed since native works.

### Idempotent index.html patching via comment markers

`patch_index_html()` in `gen_initializer.py` injects CSS, picker HTML, and JS into `dist/index.html`. To make re-runs idempotent (strip prior injection, reapply), the injection is wrapped in HTML comment markers:

```html
<!--swagger-hub:picker-begin-->
... injected content ...
<!--swagger-hub:picker-end-->
```

Earlier version used regex matching specific JS variable names (`SEARCH_MAP`, then `CATEGORIES`) — broke when the JS was refactored. Comment markers are robust against internal changes.

### GitHub Actions runner ephemerality

Runners are fresh VMs per run. Workspace destroyed when the job ends. Persistent state lives in:
- **Actions artifacts** (1–90 day retention, downloadable)
- **Actions cache** (LRU, 7-day idle eviction, 10 GB total per repo)
- **Source repo** (permanent, read via API or checkout)
- **GitHub Pages** (permanent until next deploy)

No long-lived "local cache that incrementally updates" — every run starts from zero. The Tree API + raw blob fetches in the AI engine pipeline are designed for this constraint.

### Cache key strategy

- `.deployed` cache key: `deployed-${{ steps.fetch.outputs.sha }}`. Per-SHA. Lookup is exact-match.
- `testgen-registry-*` cache key: `testgen-registry-${{ github.run_number }}` with `restore-keys: testgen-registry-`. Monotonically increasing per workflow run. `restore-keys` falls back to the most recent cache prefix-matching the key.

This means the **AI engine workflow is the only writer** of `testgen-registry-*`. Two concurrent runs would get different `run_number` values so no collision; otherwise we'd need additional locking.

### Pages site size limit

GitHub Pages site size limit is **1 GB**. Our current bundle is ~36 MB (~31 MB specs + ~5 MB Swagger UI assets). Plenty of headroom for years. If openapi-specs grows past ~700 MB of active spec content, we'd need to revisit (e.g., specs hosted off-Pages, fetched at runtime by Swagger UI).

---

## Configuration & customization points

These are the knobs to tune for the real corporate environment:

### `config/spec-categories.yml`
Category taxonomy. Maps service IDs to categories. Multi-category by listing in multiple `members:` arrays. Specs not listed anywhere fall to `default_category` ("Other / Uncategorized"). Build emits a warning per uncategorized spec but doesn't fail.

### `scripts/testgen/fetch_via_api.py`
Two filter knobs (search for `# CUSTOMIZE`):
- `SPEC_PATH_RE` — regex matching candidate spec paths in the monorepo. Default: `^services/.+-v\d+-oas\.(yaml|yml|json)$`.
- `is_retired(path)` — predicate excluding legacy/deprecated specs. Default checks for `/_legacy/`, `/legacy/`, `/deprecated/`, `/retired/` in the path. Replace with the real corporate convention (path component, filename infix, sidecar marker, OpenAPI extension field, etc.).

### `.github/workflows/portal.yml`
`sparse-checkout` patterns must match `SPEC_PATH_RE` semantics. Currently:
```yaml
sparse-checkout: |
  services/**/*-v[0-9]*-oas.yaml
  services/**/*-v[0-9]*-oas.json
  !**/_legacy/**
  !**/deprecated/**
```

These two filters (sparse-checkout + `is_retired()`) express the same business rule in two languages. Long-term, consider unifying via a shared config file.

### AI provider abstraction
`scripts/testgen/run_generation.py` has two providers: `MockProvider` and `GithubModelsProvider`. Selected via `--provider` flag or `AI_PROVIDER` env var. Adding a new provider = subclassing with a `generate(system_prompt, user_prompt) -> str` method.

### Prompts
- `prompts/system/api-testcases-system.md` — system prompt
- `prompts/templates/api-testcases-user.md` — user prompt template (uses `{{variable}}` placeholders)
- `prompts/templates/spec-gap-policy.md` — policy referenced from prompts

Prompt iteration is expected to be ongoing. Worth versioning these once we go to a real provider.

---

## File reference

### Repos
- `swagger-hub` — pipelines, scripts, prompts, config (this repo)
- `openapi-specs` (`y-didenko/openapi-specs`) — source-of-truth spec repo

### Workflows
- `.github/workflows/portal.yml` — portal pipeline (PROTOTYPE, manual)
- `.github/workflows/testgen.yml` — AI engine pipeline (PROTOTYPE, manual)
- `.github/workflows/deploy-swagger-hub.yml` — deprecated monolith (active fallback, manual)

### Scripts
- `scripts/gen_initializer.py` — picker bar + Swagger UI bootstrap; reads `config/spec-categories.yml`
- `scripts/swagger/build_manifest.py` — generates manifest from staged specs
- `scripts/swagger/validate_specs.py` — parseability checker
- `scripts/testgen/fetch_via_api.py` — Tree-API selective fetcher
- `scripts/testgen/run_generation.py` — AI engine orchestrator
- `scripts/testgen/detect_changed_specs.py` — classifies specs new/changed/unchanged via SHA-256
- `scripts/testgen/prepare_ai_input.py` — extracts AI-friendly spec representation
- `scripts/testgen/render_markdown.py` — renders AI JSON output → MD
- `scripts/testgen/update_registry.py` — merges generation result into registry (preserves `last_blob_sha`)
- `scripts/common/hashing.py` — SHA-256 helpers
- `scripts/common/io_utils.py` — JSON/YAML/text I/O
- `scripts/common/openapi_utils.py` — OpenAPI loading / introspection
- `scripts/common/models.py` — domain dataclasses

### Prompts
- `prompts/system/api-testcases-system.md`
- `prompts/templates/api-testcases-user.md`
- `prompts/templates/spec-gap-policy.md`

### Config
- `config/spec-categories.yml` — category taxonomy

### Data
- `data/manifests/` — generated manifests (not committed)
- `data/registry/processed-specs.json` — processing registry (persisted via Actions cache)
- `data/generated/testcases/` — generated MD test-case packs (artifacts)

### Docs
- `README.md` — usage / how-to-run
- `generation-spec.md` — original AI generation spec
- `split-workflows-spec.md` — split-workflow migration spec
- `api-quality-platform-deck.md` — leadership presentation
- `platform-overview.md` — this document

### Live URLs
- Portal: `https://y-didenko.github.io/swagger-hub/`

---

## Glossary

- **Active spec** — an OpenAPI document that's not retired/legacy/deprecated; the platform processes only these.
- **AI Engine** — one of the two pipelines; generates test-design and spec-quality artifacts via AI.
- **Blob SHA** — git's SHA-1 of a file's content, returned by the Tree API without downloading the file.
- **Change detection** — the per-pipeline mechanism deciding what to process. Portal uses commit SHA; AI Engine uses per-file blob SHA.
- **DarkModeToggle** — Swagger UI's native dark-mode button rendered by the standalone preset's topbar plugin.
- **Mock provider** — placeholder AI provider that returns deterministic dummy output, for pipeline testing without real AI calls.
- **Pipeline** — an end-to-end automated flow from source to delivery. We have two: Portal and AI Engine. Independent.
- **Portal** — the unified Swagger UI consumption surface; one of the two pipelines.
- **Registry** — `data/registry/processed-specs.json`; per-spec record of last-fetched blob SHA, last-processed content hash, output path, status. Persisted across runs via Actions cache.
- **Sibling features** — within the AI Engine: spec quality review and test case generation, two products with two consumers, sharing the engine.
- **Sparse-checkout** — git feature to materialize only matched paths in the working tree without fetching the full content of unmatched files.
- **Tree API** — GitHub REST endpoint `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1` that returns all paths + blob SHAs at a commit.
