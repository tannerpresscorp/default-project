# Observability

The platform logger emits JSON and offers recursive sensitive-key redaction plus configurable PII-key hooks; callers must not log raw bodies or credentials. Free-form text cannot be reliably scrubbed, and third-party/server logs are not automatically covered. HTTP tracing uses an app-local OpenTelemetry tracer provider. Set `PLATFORM_OTEL_TRACES_ENDPOINT` to the full OTLP/HTTP traces endpoint to export; without it spans are not exported. HTTP request/response header capture is disabled even if capture environment variables are set, and query strings are stripped from exported HTTP spans. The instrumentation initially constructs span attributes before its sanitizing hook; do not put secrets in URLs or install processors that inspect attributes on span start.

This foundation does not yet expose Prometheus metrics, instrument database/model/tool/workflow calls, establish correlation IDs, or provide a collector. Future metric labels must not include tenant, run, conversation or invocation IDs; high-cardinality context belongs in traces or protected logs. Audit records will require a separate queryable store.

## Sentry

Sentry error monitoring is optional in all three apps and inert without a DSN. The FastAPI platform reads `PLATFORM_SENTRY_DSN`; Django reads `SENTRY_DSN`; the React app reads `VITE_SENTRY_DSN` at build time. Each also accepts an environment name and trace sample rate (`*_SENTRY_ENVIRONMENT`, `*_SENTRY_TRACES_SAMPLE_RATE`), defaulting to `development` and `0`. DSNs must use HTTPS and belong in the environment, never in committed files; see the root and `packages/web` `.env.example` templates.

The integrations disable default PII, never send request bodies, drop query strings, cookies and form data, and redact credential-bearing headers before an event leaves the process. Sentry still receives exception messages and breadcrumb text, so callers must keep secrets out of thrown messages and URLs.
