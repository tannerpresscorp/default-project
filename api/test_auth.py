import pytest
from django.contrib.auth.models import User

from api.models import Product

PASSWORD = 'secret123'
USERNAME = 'alice'


@pytest.mark.django_db
def test_login_returns_token(client):
    User.objects.create_user(username=USERNAME, password=PASSWORD)
    response = client.post(
        '/api/auth/login/',
        data={'username': USERNAME, 'password': PASSWORD},
        content_type='application/json',
    )
    assert response.status_code == 200
    data = response.json()
    assert data['username'] == USERNAME
    assert data['token']


@pytest.mark.django_db
def test_login_rejects_bad_password(client):
    User.objects.create_user(username=USERNAME, password=PASSWORD)
    response = client.post(
        '/api/auth/login/',
        data={'username': USERNAME, 'password': 'wrong'},
        content_type='application/json',
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_token_from_login_grants_write_access(client):
    User.objects.create_user(username=USERNAME, password=PASSWORD)
    login = client.post(
        '/api/auth/login/',
        data={'username': USERNAME, 'password': PASSWORD},
        content_type='application/json',
    )
    token = login.json()['token']
    response = client.post(
        '/api/products/',
        data={'name': 'Mouse', 'price': '19.99', 'sku': 'MOUSE-001'},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Token {token}',
    )
    assert response.status_code == 201
    assert Product.objects.count() == 1