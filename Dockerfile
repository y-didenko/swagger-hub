# NOTE: services/ is injected by CI (see .github/workflows/deploy.yml).
# For local dev use docker-compose instead — it volume-mounts specs from
# the neighbouring openapi-specs repo without a build step.
FROM swaggerapi/swagger-ui:latest

COPY services/    /usr/share/nginx/html/specs/
COPY entrypoint.sh /entrypoint.sh
RUN  chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
