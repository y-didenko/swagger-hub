# swagger-hub

Centralized Swagger UI portal with AI-generated API test-case packs.

## What this does

**Job 1 — Swagger Portal** (`build` → `deploy`)
Fetches OpenAPI specs from [y-didenko/openapi-specs](https://github.com/y-didenko/openapi-specs), builds a multi-spec Swagger UI, and publishes it to GitHub Pages.

**Job 2 — Test-Case Generation** (`generate-api-testcases`)
Detects new or changed specs (compared to the processing registry), sends each spec to an AI provider as a compact structured input, and generates a markdown test-case pack per service.

---

## Workflow triggers

| Trigger | Behavior |
|---|---|
| Hourly schedule | Runs automatically; uses `mock` AI provider by default |
| `workflow_dispatch` | Manual run with configurable `ai_provider` and `force_regenerate` inputs |

---

## AI provider modes

Set via the `AI_PROVIDER` repository variable, or the `ai_provider` input on manual runs.

| Mode | Behaviour |
|---|---|
| `mock` (default) | No external calls; returns placeholder test cases. Use for pipeline validation. |
| `github-models` | Calls the GitHub Models API (OpenAI-compatible). Requires `GITHUB_TOKEN`. Model controlled by `GITHUB_MODELS_MODEL` variable (default: `gpt-4o`). |

---

## Repository structure

```
.github/workflows/
  deploy-swagger-hub.yml       Main workflow (job1 + job2)

scripts/
  gen_initializer.py           Generates swagger-initializer.js (existing)
  common/                      Shared utilities
    models.py                  Domain dataclasses
    hashing.py                 SHA-256 helpers
    io_utils.py                JSON/YAML/text I/O
    openapi_utils.py           OpenAPI loading and introspection
  swagger/
    build_manifest.py          Generates data/manifests/openapi-manifest.json
    validate_specs.py          Standalone spec parseability checker
  testgen/
    detect_changed_specs.py    Classifies specs as new/changed/unchanged
    prepare_ai_input.py        Extracts compact representation from a spec
    run_generation.py          Job2 orchestrator (main entry point)
    render_markdown.py         Renders AI output → structured markdown
    update_registry.py         Mutates the registry dict after processing

prompts/
  system/
    api-testcases-system.md    System prompt for AI generation
  templates/
    api-testcases-user.md      User prompt template (uses {{variables}})
    spec-gap-policy.md         Policy for reporting spec gaps

data/
  manifests/                   Generated manifests (not committed)
  registry/
    processed-specs.json       Processing registry (persisted via Actions cache)
  generated/testcases/         Generated markdown test-case packs (artifacts)
  fetched/                     (Reserved for local use)
```

---

## Running locally

### Prerequisites

```bash
pip install pyyaml
```

### Build a manifest

```bash
# Point at any directory of staged OpenAPI specs
python3 scripts/swagger/build_manifest.py \
  --specs-dir /path/to/specs \
  --output data/manifests/openapi-manifest.json
```

### Generate test cases (mock mode)

```bash
# Requires: data/manifests/openapi-manifest.json and specs in data/fetched/
python3 scripts/testgen/run_generation.py \
  --manifest  data/manifests/openapi-manifest.json \
  --specs-dir data/fetched \
  --provider  mock
```

Generated files appear in `data/generated/testcases/`.

### Generate test cases (GitHub Models)

```bash
export AI_PROVIDER=github-models
export GITHUB_TOKEN=<your token>
python3 scripts/testgen/run_generation.py \
  --manifest  data/manifests/openapi-manifest.json \
  --specs-dir data/fetched
```

### Prepare AI input for a single spec

```bash
python3 scripts/testgen/prepare_ai_input.py path/to/service-v1-oas.yaml
```

---

## Artifacts

| Artifact | Retention | Contents |
|---|---|---|
| `testgen-input` | 3 days | Manifest + staged specs (consumed by job2) |
| `api-testcases` | 30 days | Generated markdown + `generation-report.json` |

---

## Registry persistence

The processing registry (`data/registry/processed-specs.json`) is persisted between workflow runs using the GitHub Actions cache with the key prefix `testgen-registry-`. The most recent run's registry is restored via `restore-keys`.

To reset the registry and regenerate all specs, use the `force_regenerate: true` input on a manual run.

---

## Secrets and variables

| Name | Type | Required | Purpose |
|---|---|---|---|
| `GH_PAT` | Secret | Yes | Read access to `y-didenko/openapi-specs` |
| `AI_PROVIDER` | Variable | No | Default AI provider for scheduled runs |
| `GITHUB_MODELS_MODEL` | Variable | No | Model name for `github-models` mode (default: `gpt-4o`) |
