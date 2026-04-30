#!/usr/bin/env python3
"""
Fetch only new+changed OpenAPI specs from the openapi-specs repo via the
GitHub Tree + Git Blobs APIs.

PROTOTYPE — designed to avoid cloning the full monorepo (~440 MB / 29k files).
Compares each spec's git blob SHA against the testgen registry to decide what
to fetch. Only changed specs hit the network for content.

Outputs (compatible with run_generation.py):
  - <output-dir>/<source_path>     raw spec content for new+changed specs
  - <manifest-path>                manifest containing entries ONLY for the
                                   fetched specs (run_generation.py treats
                                   this as the universe to process)

Side effect:
  - <registry-path>                receives `last_blob_sha` for each fetched
                                   spec so the next run can skip it.

Filter customization (search this file for `# CUSTOMIZE`):
  - SPEC_PATH_RE      regex of paths considered candidate spec files
  - is_retired(path)  predicate that excludes legacy/deprecated specs
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from common.hashing import hash_content
from common.io_utils import read_json, write_json
from common.openapi_utils import detect_format, extract_info, extract_openapi_version

# ---------------------------------------------------------------------------
# CUSTOMIZE — filters for the real openapi-specs layout
# ---------------------------------------------------------------------------

# CUSTOMIZE: which paths in the monorepo are candidate spec files?
# Default matches the convention used elsewhere in this repo:
#   services/<service>/<service>-v<N>-oas.{yaml,json}
SPEC_PATH_RE = re.compile(r"^services/.+-v\d+-oas\.(yaml|yml|json)$")


def is_retired(path: str) -> bool:
    """CUSTOMIZE: return True for specs that should be excluded from generation.

    Common conventions seen in monorepos:
      - path component:   services/_legacy/...   /  services/deprecated/...
      - filename infix:   foo-deprecated-v1-oas.yaml
      - sidecar marker:   <service>/.retired
      - field-based:      info.x-status: retired (requires reading the file —
                          do that here only if the registry caches the result,
                          otherwise it defeats the purpose of the Tree API)
    """
    lowered = path.lower()
    if "/_legacy/" in lowered or "/legacy/" in lowered:
        return True
    if "/deprecated/" in lowered:
        return True
    if "/retired/" in lowered:
        return True
    return False


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

API_BASE = "https://api.github.com"


def _gh(url: str, token: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "swagger-hub-testgen",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API {exc.code} for {url}: {body}") from exc


def get_head_sha(repo: str, ref: str, token: str) -> str:
    data = json.loads(_gh(f"{API_BASE}/repos/{repo}/commits/{ref}", token))
    return data["sha"]


def get_recursive_tree(repo: str, sha: str, token: str) -> list[dict]:
    """Return all blob entries (path + git blob SHA + size) at the given commit."""
    data = json.loads(_gh(f"{API_BASE}/repos/{repo}/git/trees/{sha}?recursive=1", token))
    if data.get("truncated"):
        # The Tree API tops out at 100k entries / 7 MB. For larger repos we'd
        # need to walk subtrees. Out of scope for the prototype.
        print("WARNING: tree response was truncated; some paths may be missing", file=sys.stderr)
    return [t for t in data.get("tree", []) if t.get("type") == "blob"]


def fetch_blob(repo: str, blob_sha: str, token: str) -> bytes:
    """Fetch raw blob bytes by git blob SHA (no commit needed)."""
    data = json.loads(_gh(f"{API_BASE}/repos/{repo}/git/blobs/{blob_sha}", token))
    if data.get("encoding") != "base64":
        raise RuntimeError(f"unexpected blob encoding: {data.get('encoding')}")
    return base64.b64decode(data["content"])


# ---------------------------------------------------------------------------
# Manifest helpers (kept consistent with scripts/swagger/build_manifest.py)
# ---------------------------------------------------------------------------

def derive_service_id(rel_path: str) -> str:
    filename = Path(rel_path).name
    m = re.match(r"^(.+)-v\d+-oas\.(yaml|yml|json)$", filename)
    return m.group(1) if m else Path(filename).stem


def derive_display_name(service_id: str, info_title: str) -> str:
    if info_title:
        return info_title
    return " ".join(w.capitalize() for w in re.split(r"[-_]", service_id))


def parse_spec_bytes(content: bytes, fmt: str) -> dict:
    text = content.decode("utf-8", errors="replace")
    if fmt == "json":
        return json.loads(text)
    return yaml.safe_load(text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name of openapi-specs repo")
    parser.add_argument("--ref", default="main", help="branch / tag / SHA to operate on")
    parser.add_argument("--registry", default="data/registry/processed-specs.json")
    parser.add_argument("--output-dir", default="data/fetched")
    parser.add_argument("--manifest", default="data/manifests/openapi-manifest.json")
    parser.add_argument("--force-all", action="store_true",
                        help="Refetch every active spec, ignoring the registry")
    args = parser.parse_args()

    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GH_PAT or GITHUB_TOKEN must be set in env", file=sys.stderr)
        sys.exit(2)

    # --- 1. Resolve the SHA we operate on ---------------------------------
    sha = get_head_sha(args.repo, args.ref, token)
    print(f"openapi-specs {args.repo}@{args.ref} -> {sha}")

    # --- 2. List the recursive tree once ----------------------------------
    tree = get_recursive_tree(args.repo, sha, token)
    print(f"tree entries (blobs): {len(tree)}")

    # --- 3. Filter: candidate spec paths, minus retired ------------------
    candidates = [t for t in tree if SPEC_PATH_RE.match(t["path"])]
    active = [t for t in candidates if not is_retired(t["path"])]
    print(f"candidate specs: {len(candidates)}  active: {len(active)}  "
          f"retired: {len(candidates) - len(active)}")

    # --- 4. Load registry, decide what to fetch ---------------------------
    try:
        registry = read_json(args.registry)
    except FileNotFoundError:
        registry = {"specs": {}}
    reg_specs: dict = registry.setdefault("specs", {})

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Wipe any leftover state from a prior run inside the same workspace.
    # (CI runners are ephemeral; this matters mostly for local invocation.)
    for stale in out_dir.rglob("*-oas.*"):
        stale.unlink(missing_ok=True)

    manifest_entries: list[dict] = []
    fetched = 0
    skipped = 0

    for entry in active:
        path = entry["path"]
        blob_sha = entry["sha"]
        service_id = derive_service_id(path)

        prev = reg_specs.get(service_id, {})
        if not args.force_all and prev.get("last_blob_sha") == blob_sha:
            skipped += 1
            continue

        try:
            content = fetch_blob(args.repo, blob_sha, token)
        except Exception as exc:
            print(f"  WARN: fetch failed for {path}: {exc}", file=sys.stderr)
            continue

        target = out_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

        fmt = detect_format(path)
        try:
            spec = parse_spec_bytes(content, fmt)
            oa_version = extract_openapi_version(spec)
            info = extract_info(spec)
        except Exception as exc:
            print(f"  WARN: cannot parse {path}: {exc}", file=sys.stderr)
            oa_version, info = "unknown", {"title": "", "version": ""}

        manifest_entries.append({
            "service_id": service_id,
            "display_name": derive_display_name(service_id, info["title"]),
            "source_path": path,
            "local_path": path,
            "source_format": fmt,
            "openapi_version": oa_version,
            "info_title": info["title"],
            "info_version": info["version"],
            "spec_hash": hash_content(content.decode("utf-8", errors="replace")),
            "blob_sha": blob_sha,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_commit": sha,
            "published_url": None,
        })

        # Record the blob SHA NOW so subsequent runs skip this content even if
        # AI generation later fails on this spec.
        # PROTOTYPE caveat: a failed generation gets retried only when content
        # changes. To retry-on-failure, gate this on run_generation success
        # (move to update_registry) — see notes in this PR's description.
        existing = reg_specs.setdefault(service_id, {})
        existing["service_id"] = service_id
        existing["source_path"] = path
        existing["last_blob_sha"] = blob_sha
        existing["last_fetched_at"] = datetime.now(timezone.utc).isoformat()

        fetched += 1
        print(f"  + {service_id} ({path})")

    # --- 5. Optional: prune registry entries no longer in the active set ---
    active_ids = {derive_service_id(t["path"]) for t in active}
    pruned = [sid for sid in list(reg_specs.keys()) if sid not in active_ids]
    for sid in pruned:
        del reg_specs[sid]
    if pruned:
        print(f"pruned {len(pruned)} stale registry entries (no longer active)")

    write_json(args.registry, registry)

    # --- 6. Lean manifest with only fetched entries -----------------------
    write_json(args.manifest, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": sha,
        "specs": manifest_entries,
    })

    print()
    print(f"Fetched: {fetched}  Skipped (unchanged): {skipped}  Active total: {len(active)}")
    print(f"Manifest written: {args.manifest} ({len(manifest_entries)} entry/entries)")


if __name__ == "__main__":
    main()
