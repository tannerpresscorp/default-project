import { useEffect, useState, type FormEvent } from 'react';
import {
  ApiError,
  createApiClient,
  type PaginatedProducts,
  type Product,
} from 'api-client';

const client = createApiClient('');

interface ProductFormState {
  name: string;
  price: string;
  sku: string;
  description: string;
}

const EMPTY_FORM: ProductFormState = { name: '', price: '', sku: '', description: '' };

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.status}: ${error.message}`;
  }
  return error instanceof Error ? error.message : String(error);
}

export function App() {
  const [health, setHealth] = useState('checking…');
  const [listing, setListing] = useState<PaginatedProducts | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM);
  const [message, setMessage] = useState('');
  const [token, setToken] = useState<string | undefined>(undefined);
  const [username, setUsername] = useState('');
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const loggedIn = token !== undefined;

  useEffect(() => {
    void (async () => {
      try {
        const result = await client.health();
        setHealth(result.status);
      } catch {
        setHealth('unreachable — start the Django server (python manage.py runserver)');
      }
    })();
  }, []);

  // Reload the current page whenever the search term, page, auth state or a
  // mutation (create/delete) changes.
  useEffect(() => {
    void (async () => {
      try {
        setListing(await client.listProducts({ search: search === '' ? undefined : search, page }));
        setMessage('');
      } catch (error) {
        setMessage(messageFor(error));
      }
    })();
  }, [page, search, token, refreshKey]);

  function setField(field: keyof ProductFormState, value: string): void {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    try {
      await client.createProduct(form);
      setForm(EMPTY_FORM);
      setPage(1);
      setSearch('');
      setSearchInput('');
      setRefreshKey((key) => key + 1);
    } catch (error) {
      setMessage(messageFor(error));
    }
  }

  async function handleDelete(id: number): Promise<void> {
    try {
      await client.deleteProduct(id);
      setRefreshKey((key) => key + 1);
    } catch (error) {
      setMessage(messageFor(error));
    }
  }

  function handleSearch(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setSearch(searchInput);
    setPage(1);
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    try {
      const result = await client.login(credentials.username, credentials.password);
      client.setToken(result.token);
      setToken(result.token);
      setUsername(result.username);
      setCredentials({ username: '', password: '' });
      setMessage('');
    } catch (error) {
      setMessage(messageFor(error));
    }
  }

  function handleLogout(): void {
    client.setToken(undefined);
    setToken(undefined);
    setUsername('');
  }

  return (
    <main>
      <h1>Product Store</h1>
      <p>Health: {health}</p>

      <section aria-label="Account">
        {loggedIn ? (
          <p>
            Signed in as <strong>{username}</strong>{' '}
            <button type="button" onClick={handleLogout}>
              Log out
            </button>
          </p>
        ) : (
          <form onSubmit={(event) => void handleLogin(event)}>
            <input
              value={credentials.username}
              onChange={(event) =>
                setCredentials((prev) => ({ ...prev, username: event.target.value }))
              }
              placeholder="Username"
              autoComplete="username"
              required
            />
            <input
              value={credentials.password}
              onChange={(event) =>
                setCredentials((prev) => ({ ...prev, password: event.target.value }))
              }
              placeholder="Password"
              type="password"
              autoComplete="current-password"
              required
            />
            <button type="submit">Log in</button>
          </form>
        )}
      </section>

      <form onSubmit={(event) => void handleSubmit(event)}>
        <input
          value={form.name}
          onChange={(event) => setField('name', event.target.value)}
          placeholder="Name"
          required
        />
        <input
          value={form.price}
          onChange={(event) => setField('price', event.target.value)}
          placeholder="Price, e.g. 19.99"
          required
        />
        <input
          value={form.sku}
          onChange={(event) => setField('sku', event.target.value)}
          placeholder="SKU"
          required
        />
        <input
          value={form.description}
          onChange={(event) => setField('description', event.target.value)}
          placeholder="Description (optional)"
        />
        <button type="submit">Create product</button>
        {!loggedIn && <span>— sign in to create products</span>}
      </form>

      <form onSubmit={handleSearch}>
        <input
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Search by name, sku or description"
        />
        <button type="submit">Search</button>
      </form>

      {listing !== null && (
        <p>
          {listing.count} product{listing.count === 1 ? '' : 's'}
        </p>
      )}

      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Price</th>
            <th>SKU</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(listing?.results ?? []).map((product: Product) => (
            <tr key={product.id}>
              <td>{product.name}</td>
              <td>${product.price}</td>
              <td>{product.sku}</td>
              <td>{new Date(product.created_at).toLocaleString()}</td>
              <td>
                <button type="button" onClick={() => void handleDelete(product.id)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p>
        <button
          type="button"
          disabled={!listing?.previous}
          onClick={() => setPage((prev) => Math.max(1, prev - 1))}
        >
          Previous
        </button>{' '}
        <span>Page {page}</span>{' '}
        <button
          type="button"
          disabled={!listing?.next}
          onClick={() => setPage((prev) => prev + 1)}
        >
          Next
        </button>
      </p>

      {message !== '' && <p id="message">{message}</p>}
    </main>
  );
}