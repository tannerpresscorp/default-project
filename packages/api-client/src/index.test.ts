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

test('listProducts() GETs /api/products/ and parses the JSON array', async (t) => {
  const calls: FetchCall[] = [];
  t.mock.method(globalThis, 'fetch', async (input: unknown, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return jsonResponse([PRODUCT_JSON]);
  });

  // Trailing slash on the base URL must be stripped.
  const products = await createApiClient('http://localhost:8000/').listProducts();
  assert.equal(products.length, 1);
  assert.equal(products[0].price, '49.99');
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