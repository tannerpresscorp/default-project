/**
 * A small, dependency-free client for the companion Django products API.
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

/**
 * A product as returned by the products API.
 *
 * `price` is a string: Django REST Framework serializes `DecimalField` as a
 * string by default to preserve precision.
 */
export interface Product {
  /** Unique product identifier. */
  id: number;
  /** Product name. */
  name: string;
  /** Product description. */
  description: string;
  /** Price as a decimal string (e.g. `"19.99"`). */
  price: string;
  /** Unique stock-keeping unit. */
  sku: string;
  /** Creation timestamp (ISO 8601). */
  created_at: string;
  /** Last modification timestamp (ISO 8601). */
  updated_at: string;
}

/** Payload for creating a product. */
export interface CreateProductInput {
  /** Product name. */
  name: string;
  /** Price as a decimal string (e.g. `"19.99"`). */
  price: string;
  /** Unique stock-keeping unit. */
  sku: string;
  /** Optional product description. */
  description?: string;
}

/**
 * Payload for updating a product. Every field is optional; only the provided
 * fields are sent to the server (partial update via `PATCH`).
 */
export interface UpdateProductInput {
  /** New product name. */
  name?: string;
  /** New price as a decimal string. */
  price?: string;
  /** New stock-keeping unit. */
  sku?: string;
  /** New product description. */
  description?: string;
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
  /** List all products. Maps to `GET /api/products/`. */
  listProducts(): Promise<Product[]>;
  /** Fetch a single product by id. Maps to `GET /api/products/{id}/`. */
  getProduct(id: number): Promise<Product>;
  /** Create a product. Maps to `POST /api/products/`. */
  createProduct(input: CreateProductInput): Promise<Product>;
  /** Update a product (partial update). Maps to `PATCH /api/products/{id}/`. */
  updateProduct(id: number, input: UpdateProductInput): Promise<Product>;
  /** Delete a product. Maps to `DELETE /api/products/{id}/`. */
  deleteProduct(id: number): Promise<void>;
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

  /** Join an endpoint path (e.g. `/api/products/`) onto the base URL. */
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

    async listProducts(): Promise<Product[]> {
      return (await requestJson('/api/products/')) as Product[];
    },

    async getProduct(id: number): Promise<Product> {
      return (await requestJson(`/api/products/${id}/`)) as Product;
    },

    async createProduct(input: CreateProductInput): Promise<Product> {
      return (await requestJson('/api/products/', {
        method: 'POST',
        headers: jsonHeaders,
        body: JSON.stringify(input),
      })) as Product;
    },

    async updateProduct(id: number, input: UpdateProductInput): Promise<Product> {
      return (await requestJson(`/api/products/${id}/`, {
        method: 'PATCH',
        headers: jsonHeaders,
        body: JSON.stringify(input),
      })) as Product;
    },

    async deleteProduct(id: number): Promise<void> {
      const response = await fetch(buildUrl(`/api/products/${id}/`), { method: 'DELETE' });
      if (!response.ok) {
        throw await errorFromResponse(response);
      }
    },
  };
}