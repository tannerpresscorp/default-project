import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ApiError, createApiClient } from './index.ts';

interface FetchCall {
  url: string;
  init?: RequestInit;
}

const PRODUCT_JSON = {
  id: 1,
  name: 'Keyboard',
  description: '',
  price: '49.99',
  sku: 'KBD-001',
  created_at: '2026-10-10T00:00:00Z',
  updated_at: '2026-10-10T00:00:00Z',
};

const PAGINATED_JSON = {
  count: 1,
  next: null,
  previous: null,
  results: [PRODUCT_JSON],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function headersOf(init: RequestInit | undefined): Record<string, string> {
  return (init?.headers as Record<string, string>) ?? {};
}

test('health() GETs /api/health/ and returns the parsed JSON body', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse({ status: 'ok' });
  });

  const health = await createApiClient('http://localhost:8000').health();
  assert.deepEqual(health, { status: 'ok' });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'http://localhost:8000/api/health/');
});

test('listProducts() GETs /api/products/ and parses the paginated envelope', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse(PAGINATED_JSON);
  });

  // Trailing slashes on the base URL must be stripped.
  const result = await createApiClient('http://localhost:8000////').listProducts();
  assert.equal(result.count, 1);
  assert.equal(result.results.length, 1);
  assert.equal(result.results[0].price, '49.99');
  assert.equal(calls[0].url, 'http://localhost:8000/api/products/');
});

test('listProducts() serializes search/page/page_size into the query string', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse(PAGINATED_JSON);
  });

  await createApiClient('http://localhost:8000').listProducts({
    search: 'mouse',
    page: 2,
    page_size: 5,
  });

  const params = new URL(calls[0].url).searchParams;
  assert.equal(params.get('search'), 'mouse');
  assert.equal(params.get('page'), '2');
  assert.equal(params.get('page_size'), '5');
});

test('listProducts() omits the query string when no params are given', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse(PAGINATED_JSON);
  });

  await createApiClient('http://localhost:8000').listProducts();
  assert.equal(calls[0].url, 'http://localhost:8000/api/products/');
});

test('getProduct() GETs /api/products/{id}/ and parses the product', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse(PRODUCT_JSON);
  });

  const product = await createApiClient('http://localhost:8000').getProduct(7);
  assert.equal(product.id, 1);
  assert.equal(product.sku, 'KBD-001');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'http://localhost:8000/api/products/7/');
  assert.equal(calls[0].init?.method, undefined);
});

test('createProduct() POSTs a JSON body with the correct content-type', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse(PRODUCT_JSON, 201);
  });

  const input = { name: 'Keyboard', price: '49.99', sku: 'KBD-001', description: 'Mechanical' };
  const product = await createApiClient('http://localhost:8000').createProduct(input);

  assert.equal(product.name, 'Keyboard');
  assert.equal(calls[0].url, 'http://localhost:8000/api/products/');
  assert.equal(calls[0].init?.method, 'POST');
  assert.equal(headersOf(calls[0].init)['Content-Type'], 'application/json');
  assert.equal(headersOf(calls[0].init)['Authorization'], undefined);
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), input);
});

test('updateProduct() PATCHes /api/products/{id}/ with a JSON body', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse({ ...PRODUCT_JSON, price: '39.99' });
  });

  const product = await createApiClient('http://localhost:8000').updateProduct(3, { price: '39.99' });
  assert.equal(product.price, '39.99');
  assert.equal(calls[0].url, 'http://localhost:8000/api/products/3/');
  assert.equal(calls[0].init?.method, 'PATCH');
  assert.equal(headersOf(calls[0].init)['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), { price: '39.99' });
});

test('deleteProduct() uses method DELETE and resolves on 204', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return new Response(null, { status: 204 });
  });

  await createApiClient('http://localhost:8000').deleteProduct(5);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'http://localhost:8000/api/products/5/');
  assert.equal(calls[0].init?.method, 'DELETE');
});

test('login() POSTs /api/auth/login/ and returns the issued token', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse({ token: 'tok-123', username: 'alice' });
  });

  const result = await createApiClient('http://localhost:8000').login('alice', 'secret');
  assert.deepEqual(result, { token: 'tok-123', username: 'alice' });
  assert.equal(calls[0].url, 'http://localhost:8000/api/auth/login/');
  assert.equal(calls[0].init?.method, 'POST');
  assert.equal(headersOf(calls[0].init)['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), { username: 'alice', password: 'secret' });
});

test('a token passed at construction is sent as Authorization: Token <key>', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse(PAGINATED_JSON);
  });

  await createApiClient('http://localhost:8000', { token: 'tok-abc' }).listProducts();
  assert.equal(headersOf(calls[0].init)['Authorization'], 'Token tok-abc');
});

test('setToken() switches the auth header and undefined clears it', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse(PAGINATED_JSON);
  });

  const client = createApiClient('http://localhost:8000');
  await client.listProducts();
  assert.equal(headersOf(calls[0].init)['Authorization'], undefined);

  client.setToken('tok-xyz');
  await client.listProducts();
  assert.equal(headersOf(calls[1].init)['Authorization'], 'Token tok-xyz');

  client.setToken(undefined);
  await client.listProducts();
  assert.equal(headersOf(calls[2].init)['Authorization'], undefined);
});

test('authenticated writes merge Content-Type and Authorization headers', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse(PRODUCT_JSON, 201);
  });

  await createApiClient('http://localhost:8000', {
    token: 'tok-abc',
  }).createProduct({ name: 'Keyboard', price: '49.99', sku: 'KBD-001' });

  const headers = headersOf(calls[0].init);
  assert.equal(headers['Content-Type'], 'application/json');
  assert.equal(headers['Authorization'], 'Token tok-abc');
});

test('getProduct() rejects with an ApiError carrying status 404 and the JSON detail', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => jsonResponse({ detail: 'Not found.' }, 404));

  await assert.rejects(createApiClient('http://localhost:8000').getProduct(999), (err) => {
    assert.ok(err instanceof ApiError);
    assert.equal(err.status, 404);
    assert.equal(err.message, 'Not found.');
    return true;
  });
});

test('deleteProduct() rejects with an ApiError whose message comes from a text body', async (t) => {
  t.mock.method(
    globalThis,
    'fetch',
    async () => new Response('server blew up', { status: 500 }),
  );

  await assert.rejects(createApiClient('http://localhost:8000').deleteProduct(1), (err) => {
    assert.ok(err instanceof ApiError);
    assert.equal(err.status, 500);
    assert.equal(err.message, 'server blew up');
    return true;
  });
});

test('errors without a body fall back to the status message', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response(null, { status: 502 }));

  await assert.rejects(createApiClient('http://localhost:8000').getProduct(1), (err) => {
    assert.ok(err instanceof ApiError);
    assert.equal(err.status, 502);
    assert.equal(err.message, 'Request failed with status 502');
    return true;
  });
});