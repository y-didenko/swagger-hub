#!/usr/bin/env python3
"""Build a manifest JSON from fetched OpenAPI specs."""
import argparse
import glob
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.hashing import hash_file
from common.io_utils import write_json
from common.openapi_utils import detect_format, extract_info, extract_openapi_version, load_spec

_SPEC_GLOB_PATTERNS = [
    "**/*-v[0-9]*-oas.yaml",
    "**/*-v[0-9]*-oas.json",
]


def derive_service_id(rel_path: str) -> str:
    # Always derive from the filename so directory nesting depth doesn't matter.
    # e.g. services/notifications/notifications-v1-oas.yaml → "notifications"
    filename = Path(rel_path).name
    m = re.match(r"^(.+)-v\d+-oas\.(yaml|json)$", filename)
    if m:
        return m.group(1)
    return Path(filename).stem


def derive_display_name(service_id: str, info_title: str) -> str:
    if info_title:
        return info_title
    return " ".join(w.capitalize() for w in re.split(r"[-_]", service_id))


def build_manifest(specs_dir: str, source_commit: str = None, base_url: str = None) -> list:
    specs_path = Path(specs_dir)
    files = []
    for pattern in _SPEC_GLOB_PATTERNS:
        files += glob.glob(str(specs_path / pattern), recursive=True)
    files = sorted(set(files))

    seen_ids: dict[str, int] = {}
    entries = []

    for abs_path in files:
        rel_path = os.path.relpath(abs_path, specs_path).replace(os.sep, "/")
        service_id = derive_service_id(rel_path)

        # Deduplicate service IDs
        if service_id in seen_ids:
            seen_ids[service_id] += 1
            service_id = f"{service_id}-{seen_ids[service_id]}"
        else:
            seen_ids[service_id] = 0

        fmt = detect_format(abs_path)
        spec_hash = hash_file(abs_path)

        try:
            spec = load_spec(abs_path)
            oa_version = extract_openapi_version(spec)
            info = extract_info(spec)
            info_title = info["title"]
            info_version = info["version"]
        except Exception as exc:
            print(f"  WARNING: cannot parse {rel_path}: {exc}", file=sys.stderr)
            oa_version = "unknown"
            info_title = ""
            info_version = ""

        display_name = derive_display_name(service_id, info_title)
        published_url = None
        if base_url:
            published_url = f"{base_url.rstrip('/')}/specs/{rel_path}"

        entry = {
            "service_id": service_id,
            "display_name": display_name,
            "source_path": rel_path,
            "local_path": rel_path,  # relative; resolve against specs_dir at runtime
            "source_format": fmt,
            "openapi_version": oa_version,
            "info_title": info_title,
            "info_version": info_version,
            "spec_hash": spec_hash,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_commit": source_commit,
            "published_url": published_url,
        }
        entries.append(entry)
        print(f"  + {service_id} ({rel_path})")

    return entries


def main():
    parser = argparse.ArgumentParser(description="Build OpenAPI manifest JSON")
    parser.add_argument("--specs-dir", default="dist/specs", help="Root directory of staged specs")
    parser.add_argument("--output", default="data/manifests/openapi-manifest.json")
    parser.add_argument("--source-commit", default=None)
    parser.add_argument("--base-url", default=None, help="Published Pages base URL for published_url field")
    args = parser.parse_args()

    print(f"Scanning specs: {args.specs_dir}")
    entries = build_manifest(args.specs_dir, args.source_commit, args.base_url)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": args.source_commit,
        "specs": entries,
    }
    write_json(args.output, manifest)
    print(f"Manifest written: {args.output} ({len(entries)} spec(s))")


if __name__ == "__main__":
    main()
