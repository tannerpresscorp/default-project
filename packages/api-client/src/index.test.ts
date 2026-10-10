import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { TestContext } from 'node:test';

import { ApiError, createApiClient } from './index.ts';
import type { CreateNoteInput, Note } from './index.ts';

/** Canonical timestamp shared by the sample notes below. */
const SAMPLE_TIME = '2026-10-10T12:00:00Z';

/** Build a fully-formed note, overriding any field. */
function sampleNote(overrides: Partial<Note> = {}): Note {
  return {
    id: 1,
    title: 'Buy milk',
    body: 'Also eggs.',
    created_at: SAMPLE_TIME,
    updated_at: SAMPLE_TIME,
    ...overrides,
  };
}

/** Wrap `body` in a JSON `Response` with the given status. */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

/** A single fetch call made by the client under test. */
interface FetchCall {
  url: string;
  init: RequestInit | undefined;
}

/**
 * Replace the global `fetch` with a stub that records every call and
 * dispatches to `responder`. The mock is restored automatically when the
 * test finishes.
 */
function stubFetch(
  t: TestContext,
  responder: (input: unknown, init?: RequestInit) => Response | Promise<Response>,
): FetchCall[] {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return Promise.resolve(responder(input, init));
  });
  return calls;
}

/** Read a header from a request init, regardless of the HeadersInit form. */
function headerOf(init: RequestInit | undefined, name: string): string | null {
  const headers = init?.headers;
  if (headers === undefined) return null;
  if (headers instanceof Headers) return headers.get(name);
  if (Array.isArray(headers)) {
    const entry = headers.find(([key]) => key === name);
    return entry ? entry[1] : null;
  }
  return headers[name] ?? null;
}

test('health() GETs /api/health/ and returns the parsed JSON body', async (t) => {
  const calls = stubFetch(t, () => jsonResponse({ status: 'ok' }));
  const client = createApiClient('http://localhost:8000');

  const result = await client.health();

  assert.deepEqual(result, { status: 'ok' });
  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.url, 'http://localhost:8000/api/health/');
  assert.equal(calls[0]?.init?.method ?? 'GET', 'GET');
});

test('listNotes() GETs /api/notes/ and parses the JSON array', async (t) => {
  const notes = [sampleNote({ id: 1 }), sampleNote({ id: 2, title: 'Second note' })];
  const calls = stubFetch(t, () => jsonResponse(notes));
  // Trailing slash on the base URL must be stripped before paths are joined.
  const client = createApiClient('http://localhost:8000/');

  const result = await client.listNotes();

  assert.deepEqual(result, notes);
  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.url, 'http://localhost:8000/api/notes/');
  assert.equal(calls[0]?.init?.method ?? 'GET', 'GET');
});

test('getNote() GETs /api/notes/{id}/ and parses the note', async (t) => {
  const note = sampleNote({ id: 42, title: 'Answer' });
  const calls = stubFetch(t, () => jsonResponse(note));
  const client = createApiClient('http://localhost:8000');

  const result = await client.getNote(42);

  assert.deepEqual(result, note);
  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.url, 'http://localhost:8000/api/notes/42/');
  assert.equal(calls[0]?.init?.method ?? 'GET', 'GET');
});

test('createNote() POSTs a JSON body with the correct content-type', async (t) => {
  const created = sampleNote({ id: 3, title: 'New note', body: 'Hello' });
  const calls = stubFetch(t, () => jsonResponse(created, 201));
  const client = createApiClient('http://localhost:8000');

  const input: CreateNoteInput = { title: 'New note', body: 'Hello' };
  const result = await client.createNote(input);

  assert.deepEqual(result, created);
  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.url, 'http://localhost:8000/api/notes/');
  assert.equal(calls[0]?.init?.method, 'POST');
  assert.equal(headerOf(calls[0]?.init, 'Content-Type'), 'application/json');
  assert.deepEqual(JSON.parse(String(calls[0]?.init?.body)), input);
});

test('updateNote() PATCHes /api/notes/{id}/ with a JSON body', async (t) => {
  const updated = sampleNote({ id: 5, title: 'Renamed' });
  const calls = stubFetch(t, () => jsonResponse(updated));
  const client = createApiClient('http://localhost:8000');

  const result = await client.updateNote(5, { title: 'Renamed' });

  assert.deepEqual(result, updated);
  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.url, 'http://localhost:8000/api/notes/5/');
  assert.equal(calls[0]?.init?.method, 'PATCH');
  assert.equal(headerOf(calls[0]?.init, 'Content-Type'), 'application/json');
  assert.deepEqual(JSON.parse(String(calls[0]?.init?.body)), { title: 'Renamed' });
});

test('deleteNote() resolves on 204 using method DELETE', async (t) => {
  const calls = stubFetch(t, () => new Response(null, { status: 204 }));
  const client = createApiClient('http://localhost:8000');

  await client.deleteNote(7);

  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.url, 'http://localhost:8000/api/notes/7/');
  assert.equal(calls[0]?.init?.method, 'DELETE');
});

test('getNote() rejects with an ApiError carrying status 404 and the JSON detail', async (t) => {
  stubFetch(t, () =>
    new Response(JSON.stringify({ detail: 'Not found.' }), {
      status: 404,
      headers: { 'content-type': 'application/json' },
    }),
  );
  const client = createApiClient('http://localhost:8000');

  await assert.rejects(
    client.getNote(1),
    (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 404);
      assert.match(error.message, /Not found\./);
      return true;
    },
  );
});

test('deleteNote() rejects with an ApiError whose message comes from a text body', async (t) => {
  stubFetch(t, () => new Response('Forbidden.', { status: 403 }));
  const client = createApiClient('http://localhost:8000');

  await assert.rejects(
    client.deleteNote(1),
    (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 403);
      assert.match(error.message, /Forbidden\./);
      return true;
    },
  );
});

test('errors without a body fall back to the status message', async (t) => {
  stubFetch(t, () => new Response(null, { status: 500 }));
  const client = createApiClient('http://localhost:8000');

  await assert.rejects(
    client.health(),
    (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 500);
      assert.match(error.message, /500/);
      return true;
    },
  );
});