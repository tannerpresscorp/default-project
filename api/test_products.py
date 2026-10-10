import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from api.models import Product

PASSWORD = 'secret123'


def make_user(username='alice'):
    return User.objects.create_user(username=username, password=PASSWORD)


def auth_header(user):
    token, _created = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


@pytest.mark.django_db
def test_products_empty_list(client):
    response = client.get('/api/products/')
    assert response.status_code == 200
    assert response.json() == {'count': 0, 'next': None, 'previous': None, 'results': []}


@pytest.mark.django_db
def test_create_product_requires_auth(client):
    response = client.post(
        '/api/products/',
        data={'name': 'Mouse', 'price': '19.99', 'sku': 'M-1'},
        content_type='application/json',
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_create_product_with_token(client):
    user = make_user()
    response = client.post(
        '/api/products/',
        data={'name': 'Wireless Mouse', 'price': '19.99', 'sku': 'MOUSE-001'},
        content_type='application/json',
        **auth_header(user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data['name'] == 'Wireless Mouse'
    assert data['price'] == '19.99'  # DRF serializes DecimalField as string
    assert data['sku'] == 'MOUSE-001'
    assert 'id' in data
    assert Product.objects.count() == 1


@pytest.mark.django_db
def test_product_detail_is_public(client):
    product = Product.objects.create(name='USB Hub', price='9.50', sku='HUB-002')
    response = client.get(f'/api/products/{product.id}/')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == product.id
    assert data['price'] == '9.50'


@pytest.mark.django_db
def test_search_filters_by_name_and_sku(client):
    Product.objects.create(name='Wireless Mouse', price='19.99', sku='MOUSE-001')
    Product.objects.create(name='Keyboard', price='49.99', sku='KBD-001')
    response = client.get('/api/products/', {'search': 'mouse'})
    assert response.status_code == 200
    data = response.json()
    assert data['count'] == 1
    assert data['results'][0]['sku'] == 'MOUSE-001'

    response = client.get('/api/products/', {'search': 'KBD'})
    assert response.json()['count'] == 1
    assert response.json()['results'][0]['name'] == 'Keyboard'


@pytest.mark.django_db
def test_pagination_with_page_size(client):
    for i in range(3):
        Product.objects.create(name=f'Product {i}', price='1.00', sku=f'P-{i}')
    page1 = client.get('/api/products/', {'page_size': 2}).json()
    assert page1['count'] == 3
    assert len(page1['results']) == 2
    assert page1['next'] is not None
    assert page1['previous'] is None

    page2 = client.get('/api/products/', {'page_size': 2, 'page': 2}).json()
    assert page2['count'] == 3
    assert len(page2['results']) == 1
    assert page2['next'] is None
    assert page2['previous'] is not None


@pytest.mark.django_db
def test_delete_requires_auth(client):
    product = Product.objects.create(name='HDMI Cable', price='3.25', sku='CBL-003')
    response = client.delete(f'/api/products/{product.id}/')
    assert response.status_code == 401
    assert Product.objects.count() == 1


@pytest.mark.django_db
def test_delete_with_token(client):
    user = make_user()
    product = Product.objects.create(name='HDMI Cable', price='3.25', sku='CBL-003')
    response = client.delete(f'/api/products/{product.id}/', **auth_header(user))
    assert response.status_code == 204
    assert response.content == b''
    assert Product.objects.count() == 0