#!/usr/bin/env python3
"""Compare the manifest against the registry to classify specs as new/changed/unchanged."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.io_utils import read_json, write_json


def detect_changes(manifest_path: str, registry_path: str) -> dict:
    manifest = read_json(manifest_path)

    try:
        registry = read_json(registry_path)
    except FileNotFoundError:
        registry = {"specs": {}}

    reg_specs = registry.get("specs", {})

    new_specs, changed_specs, unchanged_specs = [], [], []

    for entry in manifest.get("specs", []):
        sid = entry["service_id"]
        current_hash = entry["spec_hash"]

        if sid not in reg_specs:
            new_specs.append(entry)
        elif reg_specs[sid].get("last_processed_hash") != current_hash:
            changed_specs.append(entry)
        else:
            unchanged_specs.append(entry)

    return {
        "new": new_specs,
        "changed": changed_specs,
        "unchanged": unchanged_specs,
    }


def main():
    parser = argparse.ArgumentParser(description="Detect new/changed/unchanged specs vs registry")
    parser.add_argument("--manifest", default="data/manifests/openapi-manifest.json")
    parser.add_argument("--registry", default="data/registry/processed-specs.json")
    parser.add_argument("--output", default=None, help="Write classification JSON to this file")
    args = parser.parse_args()

    result = detect_changes(args.manifest, args.registry)

    print(
        f"New: {len(result['new'])}  "
        f"Changed: {len(result['changed'])}  "
        f"Unchanged: {len(result['unchanged'])}"
    )

    if args.output:
        write_json(args.output, result)


if __name__ == "__main__":
    main()
