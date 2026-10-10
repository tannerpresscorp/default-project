/**
 * Hand-written entry for the generated client.
 *
 * This file lives OUTSIDE `src/` on purpose: `pnpm --filter api-client-generated
 * generate` rewrites the whole `src/` directory, so anything hand-written must
 * sit beside it. It wraps the `@hey-api/openapi-ts` output in `src/client`,
 * `src/sdk.gen.ts`, and `src/types.gen.ts` with a small, ergonomic facade:
 * pass a base URL (and optionally a token) to `createApiClient` and every call
 * resolves to data or throws, like the hand-written `api-client`.
 *
 * Regenerate the SDK with:
 *   pnpm --filter api-client-generated generate
 * (after refreshing `openapi.json` at the repo root).
 */
import { createClient } from './src/client';
import {
  authLoginCreate,
  productsCreate,
  productsDestroy,
  productsList,
  productsPartialUpdate,
  productsRetrieve,
} from './src/sdk.gen';
import type {
  LoginResponse,
  LoginRequestWritable,
  PaginatedProductList,
  PatchedProductWritable,
  Product,
  ProductWritable,
} from './src/types.gen';

export type {
  LoginRequest,
  LoginRequestWritable,
  LoginResponse,
  PaginatedProductList,
  PatchedProduct,
  PatchedProductWritable,
  Product,
  ProductWritable,
} from './src/types.gen';

export interface ApiClientOptions {
  /**
   * Server origin such as `http://localhost:8000`; a trailing slash (if any)
   * is stripped before endpoint paths are appended.
   */
  baseUrl: string;
  /**
   * Optional auth token. When set, requests carry `Authorization: Token <token>`.
   */
  token?: string;
}

/** Object returned by {@link createApiClient}. */
export interface ApiClient {
  /** Exchange username + password for a token. Maps to `POST /api/auth/login/`. */
  login(username: string, password: string): Promise<LoginResponse>;
  /**
   * List products (paginated; searchable).
   * Maps to `GET /api/products/?page=&page_size=&search=`.\
   */
  listProducts(query?: ProductsListQuery): Promise<PaginatedProductList>;
  /** Fetch a single product by id. Maps to `GET /api/products/{id}/`. */
  getProduct(id: number): Promise<Product>;
  /** Create a product. Maps to `POST /api/products/`. */
  createProduct(input: ProductWritable): Promise<Product>;
  /** Update a product (partial update). Maps to `PATCH /api/products/{id}/`. */
  updateProduct(id: number, input: PatchedProductWritable): Promise<Product>;
  /** Delete a product. Maps to `DELETE /api/products/{id}/`. */
  deleteProduct(id: number): Promise<void>;
}

/** Query parameters accepted by {@link ApiClient.listProducts}. */
export interface ProductsListQuery {
  /** A page number within the paginated result set. */
  page?: number;
  /** Number of results to return per page. */
  page_size?: number;
  /** A search term. */
  search?: string;
}

/**
 * Create an API client bound to `baseUrl`, with optional token authentication.
 *
 * Every call throws on non-2xx and resolves to the response data (the
 * generated SDK returns a `{ data, request, response }` envelope, which this
 * facade unwraps).
 */
export function createApiClient(options: ApiClientOptions): ApiClient {
  const client = createClient({
    baseUrl: options.baseUrl.replace(/\/+$/, ''),
    // The schema declares `Authorization` as a raw apiKey (no bearer prefix),
    // so send the DRF-style `Token <key>` header verbatim.
    ...(options.token !== undefined ? { auth: () => `Token ${options.token}` } : {}),
  });

  return {
    async login(username: string, password: string): Promise<LoginResponse> {
      const result = await authLoginCreate({
        client,
        body: { username, password } satisfies LoginRequestWritable,
        throwOnError: true,
      });
      return result.data;
    },

    async listProducts(query?: ProductsListQuery): Promise<PaginatedProductList> {
      const result = await productsList({ client, query, throwOnError: true });
      return result.data;
    },

    async getProduct(id: number): Promise<Product> {
      const result = await productsRetrieve({ client, path: { id }, throwOnError: true });
      return result.data;
    },

    async createProduct(input: ProductWritable): Promise<Product> {
      const result = await productsCreate({ client, body: input, throwOnError: true });
      return result.data;
    },

    async updateProduct(id: number, input: PatchedProductWritable): Promise<Product> {
      const result = await productsPartialUpdate({
        client,
        path: { id },
        body: input,
        throwOnError: true,
      });
      return result.data;
    },

    async deleteProduct(id: number): Promise<void> {
      const result = await productsDestroy({ client, path: { id }, throwOnError: true });
      return result.data;
    },
  };
}