#!/bin/sh
set -e

SPECS_DIR="/usr/share/nginx/html/specs"
INIT_JS="/usr/share/nginx/html/swagger-initializer.js"

urls=""
primary_name=""

for f in $(find "$SPECS_DIR" -name "*-v[0-9]*-oas.yaml" 2>/dev/null | sort); do
  rel=".${f#/usr/share/nginx/html}"
  filename=$(basename "$f")
  name_part=$(echo "$filename" | sed 's/-v[0-9]*-oas\.yaml$//')
  version=$(echo "$filename" | sed 's/.*-\(v[0-9]*\)-oas\.yaml$/\1/')
  label=$(echo "$name_part" | sed 's/[-_]/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2)); print}')
  entry="{\"url\":\"${rel}\",\"name\":\"${label} ${version}\"}"
  if [ -z "$urls" ]; then
    urls="$entry"
    primary_name="${label} ${version}"
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
