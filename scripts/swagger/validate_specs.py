#!/usr/bin/env python3
"""Validate that OpenAPI spec files are parseable YAML/JSON."""
import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.openapi_utils import load_spec


def validate_specs(specs_dir: str) -> tuple:
    patterns = [
        f"{specs_dir}/**/*-oas.yaml",
        f"{specs_dir}/**/*-oas.json",
    ]
    files = []
    for p in patterns:
        files += glob.glob(p, recursive=True)
    files = sorted(set(files))

    valid, invalid = [], []
    for f in files:
        try:
            load_spec(f)
            valid.append(f)
        except Exception as exc:
            invalid.append((f, str(exc)))
            print(f"  INVALID: {f}: {exc}", file=sys.stderr)

    return valid, invalid


def main():
    parser = argparse.ArgumentParser(description="Validate OpenAPI specs are parseable")
    parser.add_argument("--specs-dir", default="dist/specs")
    parser.add_argument("--fail-on-invalid", action="store_true")
    args = parser.parse_args()

    valid, invalid = validate_specs(args.specs_dir)
    print(f"Valid: {len(valid)}  Invalid: {len(invalid)}")

    if invalid and args.fail_on_invalid:
        sys.exit(1)


if __name__ == "__main__":
    main()
