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
  /* Hide only the redundant URL form (URL input / "Select definition"
     dropdown / Explore button) inside Swagger UI's topbar. The native
     Logo and DarkModeToggle stay visible. */
  .swagger-ui .topbar .download-url-wrapper { display: none; }
</style>
"""


def render_category_select(groups: list[dict], total: int) -> str:
    """Top-level category filter dropdown."""
    parts = ['<select id="api-category" aria-label="Filter by category">']
    parts.append(f'  <option value="_all">All categories ({total})</option>')
    for g in groups:
        name = g["name"].replace("&", "&amp;")
        parts.append(f'  <option value="{g["id"]}">{name} ({len(g["specs"])})</option>')
    parts.append("</select>")
    return "\n".join(parts)


def render_picker(entries: list[dict], groups: list[dict]) -> str:
    category_html = render_category_select(groups, len(entries))
    return f"""
<div id="api-picker">
  <label for="api-category">Category:</label>
  {category_html}
  <input type="search" list="api-search-list" id="api-search"
         placeholder="Search {len(entries)} APIs..." autocomplete="off"
         aria-label="Search APIs">
  <datalist id="api-search-list"></datalist>
  <span class="count" id="api-count">{len(entries)} APIs</span>
</div>
""".strip()


def render_picker_js(entries: list[dict], groups: list[dict]) -> str:
    """Emit a JS model of categories + specs and the rebuild logic."""
    # Single source of truth for the front-end: ordered categories with their specs.
    cats_data = [
        {
            "id": g["id"],
            "name": g["name"],
            "specs": [{"label": s["label"], "url": s["url"]} for s in g["specs"]],
        }
        for g in groups
    ]
    return f"""
<script>
(function() {{
  const CATEGORIES = {json.dumps(cats_data)};
  const TOTAL_APIS = {len(entries)};

  function setSpec(url) {{
    if (window.ui && window.ui.specActions && window.ui.specActions.updateUrl) {{
      window.ui.specActions.updateUrl(url);
      window.ui.specActions.download(url);
      return;
    }}
    setTimeout(function() {{ setSpec(url); }}, 100);
  }}

  function rebuild(activeCatId) {{
    const datalist = document.getElementById('api-search-list');
    const search = document.getElementById('api-search');
    const count = document.getElementById('api-count');
    datalist.innerHTML = '';

    if (activeCatId === '_all') {{
      // Datalist values include the category name so search can match either
      // the API label or the group name.
      for (const cat of CATEGORIES) {{
        for (const spec of cat.specs) {{
          const dopt = document.createElement('option');
          dopt.value = spec.label + ' — ' + cat.name;
          datalist.appendChild(dopt);
        }}
      }}
      search.placeholder = 'Search ' + TOTAL_APIS + ' APIs...';
      count.textContent = TOTAL_APIS + ' APIs';
    }} else {{
      const cat = CATEGORIES.find(function(c) {{ return c.id === activeCatId; }});
      if (!cat) return;
      for (const spec of cat.specs) {{
        const dopt = document.createElement('option');
        dopt.value = spec.label;
        datalist.appendChild(dopt);
      }}
      search.placeholder = 'Search ' + cat.specs.length + ' APIs in ' + cat.name + '...';
      count.textContent = cat.specs.length + ' / ' + TOTAL_APIS + ' APIs';
    }}
  }}

  function specByValue(value, activeCatId) {{
    if (!value) return null;
    if (activeCatId === '_all') {{
      // Datalist values are "label — categoryName"
      const sep = ' — ';
      const idx = value.lastIndexOf(sep);
      if (idx < 0) return null;
      const label = value.slice(0, idx);
      const catName = value.slice(idx + sep.length);
      const cat = CATEGORIES.find(function(c) {{ return c.name === catName; }});
      if (!cat) return null;
      return cat.specs.find(function(s) {{ return s.label === label; }}) || null;
    }} else {{
      const cat = CATEGORIES.find(function(c) {{ return c.id === activeCatId; }});
      if (!cat) return null;
      return cat.specs.find(function(s) {{ return s.label === value; }}) || null;
    }}
  }}

  document.addEventListener('DOMContentLoaded', function() {{
    const category = document.getElementById('api-category');
    const search = document.getElementById('api-search');

    rebuild(category.value);

    category.addEventListener('change', function() {{
      rebuild(category.value);
      search.value = '';
    }});

    search.addEventListener('change', function() {{
      const spec = specByValue(search.value, category.value);
      if (spec) setSpec(spec.url);
    }});
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
