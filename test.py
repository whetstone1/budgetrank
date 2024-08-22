import pytest
from flask import json
from your_app import app, db, User, Budget

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost/test_budget_leaderboard'
    client = app.test_client()

    with app.app_context():
        db.create_all()

    yield client

    with app.app_context():
        db.drop_all()

def test_leaderboard_empty(client):
    response = client.get('/leaderboard')
    assert response.status_code == 200
    assert json.loads(response.data) == []

def test_leaderboard_single_user(client):
    with app.app_context():
        user = User(username='testuser', password='testpass')
        db.session.add(user)
        db.session.commit()
        
        budget = Budget(total_income=100000, total_expenses=80000, user_id=user.id)
        db.session.add(budget)
        db.session.commit()

    response = client.get('/leaderboard')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]['username'] == 'testuser'
    assert data[0]['savings_percentage'] == 20.0

def test_leaderboard_multiple_users(client):
    with app.app_context():
        users = [
            User(username='user1', password='pass1'),
            User(username='user2', password='pass2'),
            User(username='user3', password='pass3')
        ]
        db.session.add_all(users)
        db.session.commit()

        budgets = [
            Budget(total_income=100000, total_expenses=80000, user_id=users[0].id),
            Budget(total_income=80000, total_expenses=60000, user_id=users[1].id),
            Budget(total_income=120000, total_expenses=90000, user_id=users[2].id)
        ]
        db.session.add_all(budgets)
        db.session.commit()

    response = client.get('/leaderboard')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 3
    assert data[0]['username'] == 'user3'  # Highest savings percentage
    assert data[0]['savings_percentage'] == 25.0
    assert data[1]['username'] == 'user2'
    assert data[2]['username'] == 'user1'

def test_leaderboard_income_tier_filter(client):
    with app.app_context():
        users = [
            User(username='low_income', password='pass1'),
            User(username='mid_income', password='pass2'),
            User(username='high_income', password='pass3')
        ]
        db.session.add_all(users)
        db.session.commit()

        budgets = [
            Budget(total_income=40000, total_expenses=30000, user_id=users[0].id),
            Budget(total_income=80000, total_expenses=60000, user_id=users[1].id),
            Budget(total_income=160000, total_expenses=120000, user_id=users[2].id)
        ]
        db.session.add_all(budgets)
        db.session.commit()

    response = client.get('/leaderboard?income_tier=Below 50k')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]['username'] == 'low_income'

    response = client.get('/leaderboard?income_tier=50k-100k')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]['username'] == 'mid_income'

    response = client.get('/leaderboard?income_tier=150k and above')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]['username'] == 'high_income'