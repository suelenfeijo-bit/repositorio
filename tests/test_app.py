import os
import pytest

os.environ.setdefault('FLASK_SECRET_KEY', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

from app import create_app, db

@pytest.fixture()
def app():
    app = create_app()
    with app.app_context():
        db.create_all()
    yield app

@pytest.fixture()
def client(app):
    return app.test_client()


def test_index_ok(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b'Marketplace' in res.data