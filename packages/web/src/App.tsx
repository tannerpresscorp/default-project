import { useEffect, useState, type FormEvent } from 'react';
import { ApiError, createApiClient, type Product } from 'api-client';

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
  const [products, setProducts] = useState<Product[]>([]);
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM);
  const [message, setMessage] = useState('');

  useEffect(() => {
    void (async () => {
      try {
        const result = await client.health();
        setHealth(result.status);
      } catch {
        setHealth('unreachable — start the Django server (python manage.py runserver)');
      }
      await refresh();
    })();
  }, []);

  async function refresh(): Promise<void> {
    try {
      setProducts(await client.listProducts());
      setMessage('');
    } catch (error) {
      setMessage(messageFor(error));
    }
  }

  function setField(field: keyof ProductFormState, value: string): void {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    try {
      await client.createProduct(form);
      setForm(EMPTY_FORM);
      await refresh();
    } catch (error) {
      setMessage(messageFor(error));
    }
  }

  async function handleDelete(id: number): Promise<void> {
    try {
      await client.deleteProduct(id);
      await refresh();
    } catch (error) {
      setMessage(messageFor(error));
    }
  }

  return (
    <main>
      <h1>Product Store</h1>
      <p>Health: {health}</p>

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
      </form>

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
          {products.map((product) => (
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

      {message !== '' && <p id="message">{message}</p>}
    </main>
  );
}