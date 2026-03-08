#!/bin/sh
set -e

SPECS_DIR="/usr/share/nginx/html/specs"
INIT_JS="/usr/share/nginx/html/swagger-initializer.js"

# Auto-discover every openapi.yaml / openapi.json under SPECS_DIR
# and build the SwaggerUI urls array — no hardcoded list needed.
urls=""
primary_name=""

for f in $(find "$SPECS_DIR" \( -name "openapi.yaml" -o -name "openapi.json" \) 2>/dev/null | sort); do
  rel=".${f#/usr/share/nginx/html}"
  dir=$(basename "$(dirname "$f")")
  # kebab-case / snake_case → Title Case  (e.g. "my-service" → "My Service API")
  label=$(echo "$dir" | sed 's/[-_]/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2)); print}')
  entry="{\"url\":\"${rel}\",\"name\":\"${label} API\"}"
  if [ -z "$urls" ]; then
    urls="$entry"
    primary_name="${label} API"
  else
    urls="${urls},${entry}"
  fi
done

if [ -z "$urls" ]; then
  echo "WARNING: no OpenAPI specs found under $SPECS_DIR" >&2
fi

cat > "$INIT_JS" << EOF
window.onload = function() {
  window.ui = SwaggerUIBundle({
    urls: [$urls],
    "urls.primaryName": "$primary_name",
    dom_id: "#swagger-ui",
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
    plugins: [SwaggerUIBundle.plugins.DownloadUrl],
    layout: "StandaloneLayout"
  });
};
EOF

exec nginx -g "daemon off;"
