#!/usr/bin/env python3
"""Transform an OpenAPI spec file into a compact structured representation for AI input."""
import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.io_utils import write_text
from common.openapi_utils import extract_info, extract_openapi_version, load_spec


def _summarize_schema(schema: Any, schemas: dict, depth: int = 0) -> str:
    """Return a short textual description of a schema node."""
    if not schema or depth > 3:
        return "..." if depth > 3 else ""

    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        if depth < 2:
            resolved = schemas.get(name)
            if resolved:
                return f"{name}:{{{_summarize_schema(resolved, schemas, depth + 1)}}}"
        return f"$ref:{name}"

    all_of = schema.get("allOf")
    one_of = schema.get("oneOf")
    any_of = schema.get("anyOf")
    if all_of:
        return "allOf[" + ", ".join(_summarize_schema(s, schemas, depth + 1) for s in all_of[:3]) + "]"
    if one_of:
        return "oneOf[" + ", ".join(_summarize_schema(s, schemas, depth + 1) for s in one_of[:3]) + "]"
    if any_of:
        return "anyOf[" + ", ".join(_summarize_schema(s, schemas, depth + 1) for s in any_of[:3]) + "]"

    type_ = schema.get("type", "")
    fmt = schema.get("format", "")
    enum = schema.get("enum")
    props = schema.get("properties", {})
    items = schema.get("items")
    required = schema.get("required", [])

    if type_ == "array" or items:
        item_str = _summarize_schema(items, schemas, depth + 1) if items else "any"
        return f"[{item_str}]"

    if type_ == "object" or props:
        if props:
            field_parts = []
            for fname, fschema in list(props.items())[:10]:
                req = "*" if fname in required else ""
                field_parts.append(f"{fname}{req}:{_summarize_schema(fschema, schemas, depth + 1)}")
            if len(props) > 10:
                field_parts.append(f"...+{len(props) - 10}")
            return "{" + ", ".join(field_parts) + "}"
        return "object"

    if enum:
        return f"{type_}(enum:{enum[:5]})"
    if fmt:
        return f"{type_}({fmt})"
    return type_ or "any"


def _summarize_parameter(param: dict, schemas: dict) -> dict:
    return {
        "name": param.get("name", ""),
        "in": param.get("in", ""),
        "required": param.get("required", False),
        "schema": _summarize_schema(param.get("schema", {}), schemas),
        "description": (param.get("description") or "")[:100],
    }


def _summarize_request_body(rb: dict, schemas: dict) -> dict:
    if not rb:
        return {}
    content = rb.get("content", {}) or {}
    result: dict = {"required": rb.get("required", False), "content_types": [], "schema": ""}
    for media_type, media_obj in content.items():
        result["content_types"].append(media_type)
        if not result["schema"] and isinstance(media_obj, dict) and "schema" in media_obj:
            result["schema"] = _summarize_schema(media_obj["schema"], schemas)
    return result


def _summarize_responses(responses: dict, schemas: dict) -> list:
    result = []
    for code, response in (responses or {}).items():
        if not isinstance(response, dict):
            continue
        content = response.get("content", {}) or {}
        schema_str = ""
        for _, media_obj in content.items():
            if isinstance(media_obj, dict) and "schema" in media_obj:
                schema_str = _summarize_schema(media_obj["schema"], schemas)
                break
        result.append({
            "code": code,
            "description": (response.get("description") or "")[:100],
            "schema": schema_str,
        })
    return result


def _extract_security_definitions(spec: dict) -> list:
    result = []
    # OpenAPI 3.x
    schemes = (spec.get("components") or {}).get("securitySchemes", {}) or {}
    for name, scheme in schemes.items():
        result.append({
            "name": name,
            "type": scheme.get("type", ""),
            "scheme": scheme.get("scheme", ""),
            "in": scheme.get("in", ""),
            "description": (scheme.get("description") or "")[:100],
        })
    # Swagger 2.x
    for name, scheme in (spec.get("securityDefinitions") or {}).items():
        result.append({
            "name": name,
            "type": scheme.get("type", ""),
            "in": scheme.get("in", ""),
        })
    return result


def prepare_ai_input(spec_path: str, max_endpoints: int = 100) -> dict:
    """Load *spec_path* and return a compact dict suitable as AI prompt input."""
    spec = load_spec(spec_path)
    components = spec.get("components") or {}
    schemas = components.get("schemas") or {}

    info = extract_info(spec)
    oa_version = extract_openapi_version(spec)
    paths = spec.get("paths") or {}
    http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}

    endpoints = []
    for path, path_item in list(paths.items())[:max_endpoints]:
        if not isinstance(path_item, dict):
            continue
        path_params = [
            _summarize_parameter(p, schemas) for p in (path_item.get("parameters") or [])
        ]
        for method, operation in path_item.items():
            if method.lower() not in http_methods or not isinstance(operation, dict):
                continue
            op_params = path_params + [
                _summarize_parameter(p, schemas) for p in (operation.get("parameters") or [])
            ]
            endpoints.append({
                "path": path,
                "method": method.upper(),
                "operationId": operation.get("operationId", ""),
                "tags": operation.get("tags") or [],
                "summary": (operation.get("summary") or "")[:150],
                "description": (operation.get("description") or "")[:200],
                "parameters": op_params,
                "requestBody": _summarize_request_body(operation.get("requestBody"), schemas),
                "responses": _summarize_responses(operation.get("responses", {}), schemas),
                "security": operation.get("security") or [],
                "deprecated": operation.get("deprecated", False),
            })

    return {
        "service_metadata": {
            "title": info["title"],
            "version": info["version"],
            "description": info["description"][:500],
            "openapi_version": oa_version,
        },
        "security_definitions": _extract_security_definitions(spec),
        "global_security": spec.get("security") or [],
        "endpoints": endpoints,
        "total_paths": len(paths),
        "component_schema_names": list(schemas.keys())[:50],
    }


def main():
    parser = argparse.ArgumentParser(description="Prepare compact AI input from an OpenAPI spec")
    parser.add_argument("spec_path", help="Path to the OpenAPI YAML/JSON file")
    parser.add_argument("--output", default=None, help="Write JSON output to file (default: stdout)")
    parser.add_argument("--max-endpoints", type=int, default=100)
    args = parser.parse_args()

    result = prepare_ai_input(args.spec_path, args.max_endpoints)
    output = json.dumps(result, indent=2)

    if args.output:
        write_text(args.output, output)
        print(f"Written: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
