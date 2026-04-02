# Repository: swagger-hub

This repository maintains a centralized Swagger UI portal and AI-generated API test-case packs for all services defined in the `openapi-specs` repository.

## What this repo does

- **job1** (`build` workflow job): fetches OpenAPI specs from `y-didenko/openapi-specs`, builds a multi-spec Swagger UI, deploys to GitHub Pages.
- **job2** (`generate-api-testcases` workflow job): detects new or changed specs, generates structured markdown API test-case packs via an AI provider.

## Key files for test-case generation

- `prompts/system/api-testcases-system.md` — system-level instructions for AI generation
- `prompts/templates/api-testcases-user.md` — user prompt template (variables in `{{...}}`)
- `prompts/copilot/generate-testcases.md` — **self-contained instruction for direct Copilot use**
- `scripts/testgen/render_markdown.py` — defines the final markdown output structure
- `data/registry/processed-specs.json` — tracks which specs have already been processed

## OpenAPI specs location

All source specs live in `y-didenko/openapi-specs` under `services/<name>/<name>-v<n>-oas.yaml`.

## Output format

Each generated test-case pack is a markdown file following the structure defined in `scripts/testgen/render_markdown.py`. Test cases use sequential IDs (TC-001, TC-002, …).
