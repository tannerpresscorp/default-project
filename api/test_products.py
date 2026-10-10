import pytest

from api.models import Product


@pytest.mark.django_db
def test_products_empty_list(client):
    response = client.get('/api/products/')
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_create_product(client):
    response = client.post(
        '/api/products/',
        data={'name': 'Wireless Mouse', 'price': '19.99', 'sku': 'MOUSE-001'},
        content_type='application/json',
    )
    assert response.status_code == 201
    data = response.json()
    assert data['name'] == 'Wireless Mouse'
    assert data['price'] == '19.99'  # DRF serializes DecimalField as string
    assert data['sku'] == 'MOUSE-001'
    assert 'id' in data
    assert 'created_at' in data
    assert 'updated_at' in data
    assert Product.objects.count() == 1


@pytest.mark.django_db
def test_product_detail(client):
    product = Product.objects.create(name='USB Hub', price='9.50', sku='HUB-002')
    response = client.get(f'/api/products/{product.id}/')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == product.id
    assert data['name'] == 'USB Hub'
    assert data['price'] == '9.50'
    assert data['sku'] == 'HUB-002'


@pytest.mark.django_db
def test_delete_product(client):
    product = Product.objects.create(name='HDMI Cable', price='3.25', sku='CBL-003')
    response = client.delete(f'/api/products/{product.id}/')
    assert response.status_code == 204
    assert response.content == b''
    assert Product.objects.count() == 0