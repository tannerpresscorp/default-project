/**
 * A small, dependency-free client for the companion Django notes API.
 *
 * `createApiClient` returns a typed facade over the global `fetch`, so this
 * package has no runtime dependencies and works anywhere Node's `fetch` is
 * available (Node 18+).
 */

/** Response shape of `GET /api/health/`. */
export interface HealthResponse {
  /** Server health status. */
  status: 'ok';
}

/** A note as returned by the notes API. */
export interface Note {
  /** Unique note identifier. */
  id: number;
  /** Note title. */
  title: string;
  /** Note body content. */
  body: string;
  /** Creation timestamp (ISO 8601). */
  created_at: string;
  /** Last modification timestamp (ISO 8601). */
  updated_at: string;
}

/** Payload for creating a note. */
export interface CreateNoteInput {
  /** Note title. */
  title: string;
  /** Optional note body. */
  body?: string;
}

/**
 * Payload for updating a note. Every field is optional; only the provided
 * fields are sent to the server (partial update via `PATCH`).
 */
export interface UpdateNoteInput {
  /** New note title. */
  title?: string;
  /** New note body. */
  body?: string;
}

/** Error thrown when the API responds with a non-2xx status. */
export class ApiError extends Error {
  /** HTTP status code returned by the server. */
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** Object returned by {@link createApiClient}. */
export interface ApiClient {
  /** Fetch server health. Maps to `GET /api/health/`. */
  health(): Promise<HealthResponse>;
  /** List all notes. Maps to `GET /api/notes/`. */
  listNotes(): Promise<Note[]>;
  /** Fetch a single note by id. Maps to `GET /api/notes/{id}/`. */
  getNote(id: number): Promise<Note>;
  /** Create a note. Maps to `POST /api/notes/`. */
  createNote(input: CreateNoteInput): Promise<Note>;
  /** Update a note (partial update). Maps to `PATCH /api/notes/{id}/`. */
  updateNote(id: number, input: UpdateNoteInput): Promise<Note>;
  /** Delete a note. Maps to `DELETE /api/notes/{id}/`. */
  deleteNote(id: number): Promise<void>;
}

/**
 * Build an {@link ApiError} from a non-2xx response, preferring a message
 * read from the response body when one is available.
 */
async function errorFromResponse(response: Response): Promise<ApiError> {
  const fallback = `Request failed with status ${response.status}`;
  let message: string | undefined;

  try {
    const contentType = response.headers.get('content-type') ?? '';
    const raw: unknown = contentType.includes('application/json')
      ? await response.json()
      : await response.text();

    if (typeof raw === 'string') {
      message = raw;
    } else if (isRecord(raw)) {
      const detail = raw.detail;
      message = typeof detail === 'string' ? detail : JSON.stringify(raw);
    }
  } catch {
    // Ignore body read/parse failures; fall back to the status message.
  }

  return new ApiError(response.status, message && message.length > 0 ? message : fallback);
}

/** Narrow a value to a string-keyed record. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/**
 * Create an API client bound to `baseUrl`.
 *
 * `baseUrl` is a server origin such as `http://localhost:8000`; a trailing
 * slash (if any) is stripped before endpoint paths are appended.
 */
export function createApiClient(baseUrl: string): ApiClient {
  const base = baseUrl.replace(/\/+$/, '');

  /** Join an endpoint path (e.g. `/api/notes/`) onto the base URL. */
  const buildUrl = (path: string): string => `${base}${path}`;

  /** Send a request and return the JSON body of a 2xx response. */
  async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
    const response = await fetch(buildUrl(path), init);
    if (!response.ok) {
      throw await errorFromResponse(response);
    }
    const body: unknown = await response.json();
    return body;
  }

  /** Headers used for requests that carry a JSON body. */
  const jsonHeaders = { 'Content-Type': 'application/json' };

  return {
    async health(): Promise<HealthResponse> {
      return (await requestJson('/api/health/')) as HealthResponse;
    },

    async listNotes(): Promise<Note[]> {
      return (await requestJson('/api/notes/')) as Note[];
    },

    async getNote(id: number): Promise<Note> {
      return (await requestJson(`/api/notes/${id}/`)) as Note;
    },

    async createNote(input: CreateNoteInput): Promise<Note> {
      return (await requestJson('/api/notes/', {
        method: 'POST',
        headers: jsonHeaders,
        body: JSON.stringify(input),
      })) as Note;
    },

    async updateNote(id: number, input: UpdateNoteInput): Promise<Note> {
      return (await requestJson(`/api/notes/${id}/`, {
        method: 'PATCH',
        headers: jsonHeaders,
        body: JSON.stringify(input),
      })) as Note;
    },

    async deleteNote(id: number): Promise<void> {
      const response = await fetch(buildUrl(`/api/notes/${id}/`), { method: 'DELETE' });
      if (!response.ok) {
        throw await errorFromResponse(response);
      }
    },
  };
}