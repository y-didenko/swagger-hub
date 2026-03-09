import os, glob, re

specs = sorted(glob.glob("dist/specs/**/*-v[0-9]*-oas.yaml", recursive=True))
urls = []
for path in specs:
    filename = os.path.basename(path)
    m = re.match(r'^(.+)-(v\d+)-oas\.yaml$', filename)
    if m:
        label = " ".join(w.capitalize() for w in re.split(r"[-_]", m.group(1))) + f" {m.group(2)}"
    else:
        label = os.path.splitext(filename)[0]
    rel = "./" + path[len("dist/"):]
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
