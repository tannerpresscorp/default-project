import pytest

from api.models import Note


@pytest.mark.django_db
def test_notes_empty_list(client):
    response = client.get('/api/notes/')
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_create_note(client):
    response = client.post(
        '/api/notes/',
        data={'title': 'My note', 'body': 'Hello world'},
        content_type='application/json',
    )
    assert response.status_code == 201
    data = response.json()
    assert data['title'] == 'My note'
    assert data['body'] == 'Hello world'
    assert 'id' in data
    assert 'created_at' in data
    assert 'updated_at' in data
    assert Note.objects.count() == 1


@pytest.mark.django_db
def test_note_detail(client):
    note = Note.objects.create(title='Detail me', body='Body text')
    response = client.get(f'/api/notes/{note.id}/')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == note.id
    assert data['title'] == 'Detail me'
    assert data['body'] == 'Body text'


@pytest.mark.django_db
def test_delete_note(client):
    note = Note.objects.create(title='Delete me', body='Gone soon')
    response = client.delete(f'/api/notes/{note.id}/')
    assert response.status_code == 204
    assert response.content == b''
    assert Note.objects.count() == 0