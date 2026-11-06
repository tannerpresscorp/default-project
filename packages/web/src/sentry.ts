import * as Sentry from '@sentry/react';
import type { ErrorEvent } from '@sentry/react';

const SENSITIVE_HEADERS = new Set([
  'authorization',
  'cookie',
  'proxy-authorization',
  'set-cookie',
  'x-api-key',
]);

const SENSITIVE_KEY = /authorization|password|secret|api.?key|token|credential/i;
const BEARER = /\bBearer\s+\S+/gi;

export function redact(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(redact);
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        SENSITIVE_KEY.test(key) ? '[REDACTED]' : redact(item),
      ]),
    );
  }
  if (typeof value === 'string') {
    return value.replace(BEARER, 'Bearer [REDACTED]');
  }
  return value;
}

/** Remove credentials and payloads before an event leaves the browser. */
export function scrubEvent(event: ErrorEvent): ErrorEvent {
  const request = event.request;
  if (request) {
    if (request.headers) {
      for (const key of Object.keys(request.headers)) {
        if (SENSITIVE_HEADERS.has(key.toLowerCase())) {
          request.headers[key] = '[REDACTED]';
        }
      }
    }
    delete request.cookies;
    delete request.data;
    delete request.query_string;
  }
  if (event.extra) {
    event.extra = redact(event.extra) as Record<string, unknown>;
  }
  if (event.contexts) {
    event.contexts = redact(event.contexts) as ErrorEvent['contexts'];
  }
  if (event.tags) {
    event.tags = redact(event.tags) as Record<string, string>;
  }
  if (event.breadcrumbs) {
    for (const breadcrumb of event.breadcrumbs) {
      if (breadcrumb.data) {
        breadcrumb.data = redact(breadcrumb.data) as Record<string, unknown>;
      }
      if (breadcrumb.message) {
        breadcrumb.message = redact(breadcrumb.message) as string;
      }
    }
  }
  return event;
}

/** Initialize Sentry only when a DSN is configured at build time. */
export function initSentry(): boolean {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) {
    return false;
  }
  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT ?? 'development',
    tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0),
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
      stackFrameVariables: false,
      graphQL: { document: false, variables: false },
    },
    integrations: [Sentry.browserTracingIntegration()],
    beforeSend: scrubEvent,
  });
  return true;
}
