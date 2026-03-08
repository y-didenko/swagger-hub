import os, glob, re

specs = sorted(
    glob.glob("dist/specs/**/openapi.yaml", recursive=True) +
    glob.glob("dist/specs/**/openapi.json", recursive=True)
)
urls = []
for path in specs:
    rel   = "./" + path[len("dist/"):]
    name  = os.path.basename(os.path.dirname(path))
    label = " ".join(w.capitalize() for w in re.split(r"[-_]", name)) + " API"
    urls.append(f'{{"url":"{rel}","name":"{label}"}}')

primary = urls[0].split('"name":"')[1].rstrip('"}') if urls else ""

with open("dist/swagger-initializer.js", "w") as f:
    f.write(f"""window.onload = function() {{
  window.ui = SwaggerUIBundle({{
    urls: [{", ".join(urls)}],
    "urls.primaryName": "{primary}",
    dom_id: "#swagger-ui",
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
    plugins: [SwaggerUIBundle.plugins.DownloadUrl],
    layout: "StandaloneLayout"
  }});
}};
""")
print(f"swagger-initializer.js -> {len(urls)} spec(s) registered")
