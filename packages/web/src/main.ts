import { ApiError, createApiClient } from 'api-client';

const client = createApiClient('');

const statusEl = document.querySelector<HTMLParagraphElement>('#health');
const messageEl = document.querySelector<HTMLParagraphElement>('#message');
const form = document.querySelector<HTMLFormElement>('#create-product');
const tbody = document.querySelector<HTMLTableSectionElement>('#products');

function showMessage(text: string): void {
  if (messageEl) messageEl.textContent = text;
}

async function loadProducts(): Promise<void> {
  const products = await client.listProducts();
  renderProducts(products);
}

function renderProducts(products: Awaited<ReturnType<typeof client.listProducts>>): void {
  if (!tbody) return;
  tbody.replaceChildren();

  for (const product of products) {
    const row = document.createElement('tr');

    const name = document.createElement('td');
    name.textContent = product.name;
    const price = document.createElement('td');
    price.textContent = `$${product.price}`;
    const sku = document.createElement('td');
    sku.textContent = product.sku;
    const created = document.createElement('td');
    created.textContent = new Date(product.created_at).toLocaleString();

    const actions = document.createElement('td');
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = 'Delete';
    remove.addEventListener('click', () => void deleteProduct(product.id));
    actions.append(remove);

    row.append(name, price, sku, created, actions);
    tbody.append(row);
  }
}

async function deleteProduct(id: number): Promise<void> {
  try {
    await client.deleteProduct(id);
    showMessage('');
    await loadProducts();
  } catch (error) {
    reportError(error);
  }
}

function reportError(error: unknown): void {
  if (error instanceof ApiError) {
    showMessage(`${error.status}: ${error.message}`);
  } else {
    showMessage(error instanceof Error ? error.message : String(error));
  }
}

async function createProductFromForm(event: Event): Promise<void> {
  event.preventDefault();
  if (!form) return;

  const data = new FormData(form);
  const name = String(data.get('name') ?? '');
  const price = String(data.get('price') ?? '');
  const sku = String(data.get('sku') ?? '');
  const description = String(data.get('description') ?? '');

  try {
    await client.createProduct({ name, price, sku, description });
    showMessage('');
    form.reset();
    await loadProducts();
  } catch (error) {
    reportError(error);
  }
}

async function init(): Promise<void> {
  if (statusEl) {
    try {
      const health = await client.health();
      statusEl.textContent = `Health: ${health.status}`;
    } catch (error) {
      statusEl.textContent =
        'Health: unreachable — start the Django server (python manage.py runserver)';
      reportError(error);
    }
  }

  try {
    await loadProducts();
  } catch (error) {
    reportError(error);
  }
}

form?.addEventListener('submit', (event) => void createProductFromForm(event));
void init();