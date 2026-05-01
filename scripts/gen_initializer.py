#!/usr/bin/env python3
"""
Generate the Swagger UI initializer JS and inject a categorized search picker
into dist/index.html.

Inputs:
    dist/specs/**/*-v[0-9]*-oas.{yaml,json}    discovered specs
    config/spec-categories.yml                 category mapping (optional)

Outputs:
    dist/swagger-initializer.js                Swagger UI bootstrap
    dist/index.html (patched)                  picker bar injected before #swagger-ui

The picker is built from native HTML primitives:
    <input list="...">  +  <datalist>     →  search-as-you-type (browser-handled)
    <select> + <optgroup>                  →  categorized browse (browser-handled)

About 25 lines of glue JS wires both controls into Swagger UI's specActions.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

SPEC_GLOBS = [
    "dist/specs/**/*-v[0-9]*-oas.yaml",
    "dist/specs/**/*-v[0-9]*-oas.json",
]


def discover_specs() -> list[dict]:
    paths: list[str] = []
    for g in SPEC_GLOBS:
        paths += glob.glob(g, recursive=True)
    paths = sorted(set(paths))

    entries: list[dict] = []
    for path in paths:
        filename = os.path.basename(path)
        m = re.match(r"^(.+)-(v\d+)-oas\.(yaml|yml|json)$", filename)
        if m:
            service_id = m.group(1)
            version = m.group(2)
            label = (
                " ".join(w.capitalize() for w in re.split(r"[-_]", service_id))
                + f" {version}"
            )
        else:
            service_id = os.path.splitext(filename)[0]
            version = ""
            label = service_id
        rel_url = "./" + path[len("dist/"):]
        entries.append({
            "service_id": service_id,
            "version": version,
            "label": label,
            "url": rel_url,
        })
    return entries


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "default_category": {"id": "other", "name": "Other / Uncategorized"},
    "categories": [],
}


def load_categories_config(path: str = "config/spec-categories.yml") -> dict:
    if not Path(path).exists():
        print(f"INFO: {path} not found; all specs go to 'Other'", file=sys.stderr)
        return DEFAULT_CONFIG
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    return {
        "default_category": cfg.get("default_category", DEFAULT_CONFIG["default_category"]),
        "categories": cfg.get("categories", []),
    }


def group_specs(entries: list[dict], cfg: dict) -> tuple[list[dict], list[dict]]:
    """Return (ordered_groups, uncategorized_entries).

    Each group is `{id, name, specs: [entry, ...]}` where a spec MAY appear in
    multiple groups (multi-category support).
    """
    by_id = {e["service_id"]: e for e in entries}
    in_any: set[str] = set()
    groups: list[dict] = []

    for cat in cfg.get("categories", []):
        cat_id = cat["id"]
        cat_name = cat["name"]
        members = cat.get("members", []) or []
        cat_specs = []
        for m in members:
            if m in by_id:
                cat_specs.append(by_id[m])
                in_any.add(m)
            else:
                print(f"WARN: category '{cat_id}' references unknown spec '{m}'",
                      file=sys.stderr)
        if cat_specs:
            groups.append({"id": cat_id, "name": cat_name, "specs": cat_specs})

    uncategorized = [e for e in entries if e["service_id"] not in in_any]
    if uncategorized:
        d = cfg["default_category"]
        groups.append({"id": d["id"], "name": d["name"], "specs": uncategorized})

    return groups, uncategorized


# ---------------------------------------------------------------------------
# HTML / JS rendering
# ---------------------------------------------------------------------------

PICKER_CSS = """
<style>
  body { margin: 0; }
  #api-picker {
    display: flex;
    gap: 0.75rem;
    padding: 0.6rem 1rem;
    background: #1b1b1b;
    border-bottom: 1px solid #333;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 100;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  #api-picker label {
    color: #ddd;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    margin-right: 0.5rem;
  }
  #api-picker input,
  #api-picker select {
    font-size: 0.95rem;
    padding: 0.45rem 0.75rem;
    border: 1px solid #444;
    border-radius: 4px;
    background: #fff;
    color: #1b1b1b;
  }
  #api-picker input { flex: 1; max-width: 520px; }
  #api-picker select { min-width: 280px; max-width: 360px; }
  #api-picker input:focus,
  #api-picker select:focus {
    outline: 2px solid #4990e2;
    outline-offset: 1px;
  }
  #api-picker .count {
    color: #888;
    font-size: 0.8rem;
    margin-left: auto;
  }
</style>
"""


def render_select(groups: list[dict]) -> str:
    parts = ['<select id="api-browser" aria-label="Browse APIs by category">']
    for g in groups:
        # Escape minimal HTML-special chars in category name
        name = g["name"].replace("&", "&amp;")
        parts.append(f'  <optgroup label="{name} ({len(g["specs"])})">')
        for spec in g["specs"]:
            parts.append(
                f'    <option value="{spec["url"]}" data-name="{spec["label"]}">'
                f'{spec["label"]}</option>'
            )
        parts.append("  </optgroup>")
    parts.append("</select>")
    return "\n".join(parts)


def render_datalist(groups: list[dict]) -> str:
    parts = ['<datalist id="api-search-list">']
    for g in groups:
        name = g["name"].replace("&", "&amp;")
        for spec in g["specs"]:
            value = f'{spec["label"]} — {name}'
            parts.append(f'  <option value="{value}">')
    parts.append("</datalist>")
    return "\n".join(parts)


def render_picker(entries: list[dict], groups: list[dict]) -> str:
    select_html = render_select(groups)
    datalist_html = render_datalist(groups)
    return f"""
<div id="api-picker">
  <label for="api-search">API:</label>
  <input type="search" list="api-search-list" id="api-search"
         placeholder="Search {len(entries)} APIs..." autocomplete="off"
         aria-label="Search APIs">
  {datalist_html}
  {select_html}
  <span class="count">{len(entries)} APIs</span>
</div>
""".strip()


def render_picker_js(entries: list[dict], groups: list[dict]) -> str:
    """Build the search-value → {url, name} map and the wire-up JS."""
    search_map: dict[str, dict] = {}
    for g in groups:
        cat_name = g["name"]
        for spec in g["specs"]:
            search_map[f'{spec["label"]} — {cat_name}'] = {
                "url": spec["url"], "name": spec["label"],
            }
    return f"""
<script>
(function() {{
  const SEARCH_MAP = {json.dumps(search_map)};
  function setSpec(url, name) {{
    if (window.ui && window.ui.specActions && window.ui.specActions.updateUrl) {{
      window.ui.specActions.updateUrl(url);
      window.ui.specActions.download(url);
      return;
    }}
    // Swagger UI not yet ready — retry shortly.
    setTimeout(function() {{ setSpec(url, name); }}, 100);
  }}
  document.addEventListener('DOMContentLoaded', function() {{
    const search = document.getElementById('api-search');
    const browser = document.getElementById('api-browser');
    if (search) {{
      search.addEventListener('change', function() {{
        const entry = SEARCH_MAP[search.value];
        if (entry) {{
          setSpec(entry.url, entry.name);
          if (browser) browser.value = entry.url;
        }}
      }});
    }}
    if (browser) {{
      browser.addEventListener('change', function() {{
        const opt = browser.options[browser.selectedIndex];
        if (!opt || !opt.value) return;
        const name = opt.getAttribute('data-name') || opt.textContent;
        setSpec(opt.value, name);
        if (search) search.value = '';
      }});
    }}
  }});
}})();
</script>
""".strip()


# ---------------------------------------------------------------------------
# Patch index.html
# ---------------------------------------------------------------------------

def patch_index_html(path: str, css: str, picker_html: str, js: str) -> None:
    with open(path) as f:
        html = f.read()

    if "api-picker" in html:
        # Already patched — strip our previous injection and reapply (idempotent).
        html = re.sub(
            r"<style>\s*body \{ margin: 0; \}\s*#api-picker.*?</style>",
            "", html, count=1, flags=re.DOTALL,
        )
        html = re.sub(
            r'<div id="api-picker">.*?</div>\s*',
            "", html, count=1, flags=re.DOTALL,
        )
        html = re.sub(
            r"<script>\s*\(function\(\) \{\s*const SEARCH_MAP.*?</script>",
            "", html, count=1, flags=re.DOTALL,
        )

    html = html.replace("</head>", css + "</head>", 1)
    html = html.replace(
        '<div id="swagger-ui"></div>',
        picker_html + '\n<div id="swagger-ui"></div>',
        1,
    )
    html = html.replace("</body>", js + "\n</body>", 1)

    with open(path, "w") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Initializer JS
# ---------------------------------------------------------------------------

def write_initializer(entries: list[dict]) -> None:
    if not entries:
        primary_url = ""
    else:
        primary_url = entries[0]["url"]

    body = f"""window.onload = function() {{
  window.ui = SwaggerUIBundle({{
    url: {json.dumps(primary_url)},
    dom_id: "#swagger-ui",
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
    plugins: [SwaggerUIBundle.plugins.DownloadUrl],
    layout: "StandaloneLayout"
  }});
}};
"""
    with open("dist/swagger-initializer.js", "w") as f:
        f.write(body)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    entries = discover_specs()
    cfg = load_categories_config()
    groups, uncategorized = group_specs(entries, cfg)

    write_initializer(entries)

    css = PICKER_CSS
    picker_html = render_picker(entries, groups)
    picker_js = render_picker_js(entries, groups)
    patch_index_html("dist/index.html", css, picker_html, picker_js)

    print(f"swagger-initializer.js -> {len(entries)} spec(s) registered")
    print(f"index.html             -> picker injected, {len(groups)} group(s)")
    if uncategorized:
        print(f"  ⚠ {len(uncategorized)} uncategorized spec(s) → '{cfg['default_category']['name']}':")
        for s in uncategorized:
            print(f"      - {s['service_id']}")
    multi_category = {}
    for g in groups:
        for s in g["specs"]:
            multi_category.setdefault(s["service_id"], []).append(g["name"])
    cross_listed = {sid: cats for sid, cats in multi_category.items() if len(cats) > 1}
    if cross_listed:
        print(f"  ↔ {len(cross_listed)} cross-listed spec(s):")
        for sid, cats in sorted(cross_listed.items()):
            print(f"      - {sid}: {', '.join(cats)}")


if __name__ == "__main__":
    main()
