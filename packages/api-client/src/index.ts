/**
 * A small, dependency-free client for the companion Django products API.
 *
 * `createApiClient` returns a typed facade over the global `fetch`, so this
 * package has no runtime dependencies and works anywhere Node's `fetch` is
 * available (Node 18+).
 *
 * Authenticated endpoints use DRF token auth: pass a token to
 * `createApiClient`, set one later via {@link ApiClient.setToken}, or obtain
 * one with {@link ApiClient.login}. When a token is set, every request carries
 * `Authorization: Token <key>`.
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

/**
 * One page of products as returned by `GET /api/products/` (the server uses
 * page-number pagination by default).
 */
export interface PaginatedProducts {
  /** Total number of matching products across all pages. */
  count: number;
  /** URL of the next page, or `null` on the last page. */
  next: string | null;
  /** URL of the previous page, or `null` on the first page. */
  previous: string | null;
  /** Products on this page. */
  results: Product[];
}

/** Query parameters accepted by `GET /api/products/`. */
export interface ListProductsParams {
  /** Free-text search across name, sku and description. */
  search?: string;
  /** Page number (1-based). */
  page?: number;
  /** Number of results per page. */
  page_size?: number;
}

/** Result of a successful `POST /api/auth/login/`. */
export interface LoginResult {
  /** Token to send as `Authorization: Token <key>`. */
  token: string;
  /** Username that was logged in. */
  username: string;
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
  /** Set (or clear, with `undefined`) the token sent as `Authorization: Token <key>`. */
  setToken(token: string | undefined): void;
  /** Exchange username + password for a token. Maps to `POST /api/auth/login/`. */
  login(username: string, password: string): Promise<LoginResult>;
  /**
   * List products (paginated; searchable). Maps to `GET /api/products/`.
   * The server caps `page_size` at 100 and defaults it to 10.
   */
  listProducts(params?: ListProductsParams): Promise<PaginatedProducts>;
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
 * slash (if any) is stripped before endpoint paths are appended. Pass an
 * optional initial token (or call `setToken` later) to authenticate requests.
 */
export function createApiClient(baseUrl: string, options: { token?: string } = {}): ApiClient {
  let baseEnd = baseUrl.length;
  while (baseEnd > 0 && baseUrl[baseEnd - 1] === '/') baseEnd--;
  const base = baseUrl.slice(0, baseEnd);
  let token: string | undefined = options.token;

  /** Join an endpoint path (e.g. `/api/products/`) onto the base URL. */
  const buildUrl = (path: string): string => `${base}${path}`;

  /** Merge the auth header into a request's headers when a token is set. */
  const withAuth = (headers: Record<string, string> = {}): Record<string, string> =>
    token !== undefined ? { ...headers, Authorization: `Token ${token}` } : headers;

  /** Send a request and return the parsed body of a 2xx response. */
  async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
    const response = await fetch(buildUrl(path), { ...init, headers: withAuth(init?.headers as Record<string, string> | undefined) });
    if (!response.ok) {
      throw await errorFromResponse(response);
    }
    const body: unknown = await response.json();
    return body;
  }

  return {
    async health(): Promise<HealthResponse> {
      return (await requestJson('/api/health/')) as HealthResponse;
    },

    setToken(next: string | undefined): void {
      token = next;
    },

    async login(username: string, password: string): Promise<LoginResult> {
      return (await requestJson('/api/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })) as LoginResult;
    },

    async listProducts(params: ListProductsParams = {}): Promise<PaginatedProducts> {
      const query = new URLSearchParams();
      if (params.search !== undefined) query.set('search', params.search);
      if (params.page !== undefined) query.set('page', String(params.page));
      if (params.page_size !== undefined) query.set('page_size', String(params.page_size));
      const queryString = query.toString();
      const path = queryString.length > 0 ? `/api/products/?${queryString}` : '/api/products/';
      return (await requestJson(path)) as PaginatedProducts;
    },

    async getProduct(id: number): Promise<Product> {
      return (await requestJson(`/api/products/${id}/`)) as Product;
    },

    async createProduct(input: CreateProductInput): Promise<Product> {
      return (await requestJson('/api/products/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      })) as Product;
    },

    async updateProduct(id: number, input: UpdateProductInput): Promise<Product> {
      return (await requestJson(`/api/products/${id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      })) as Product;
    },

    async deleteProduct(id: number): Promise<void> {
      const response = await fetch(buildUrl(`/api/products/${id}/`), {
        method: 'DELETE',
        headers: withAuth(),
      });
      if (!response.ok) {
        throw await errorFromResponse(response);
      }
    },
  };
}