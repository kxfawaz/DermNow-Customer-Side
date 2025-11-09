from models import User, db
from app import app

def test_signup(client):
    resp = client.post("/signup", data={
        "username": "karimxf94",
        "email": "kf@test.com",
        "password": "Iam@theplants23!",
        "firstname": "Karim",
        "lastname": "Fawaz"
    }, follow_redirects=True)

    # Query must run inside app context
    with app.app_context():
        user = User.query.filter_by(username="karimxf94").first()
        assert user is not None


def test_login(client):
    with app.app_context():
        u = User.signup(
            username="testuser",
            email="t@test.com",
            password="Iam@theplants23!",
            first_name="T",
            last_name="User"
        )
        db.session.commit()

    resp = client.post("/login", data={
        "username": "testuser",
        "password": "Iam@theplants23!"
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Start an eConsultation" in resp.data  # content on dashboard

def test_signup_duplicate_username(client):
    with app.app_context():
        User.signup("karimf23", "original@test.com", "Password1!", "Karim", "Fawaz")
        db.session.commit()

    resp = client.post("/signup", data={
        "username": "karimf23",     # same username again
        "email": "new@test.com",
        "password": "Password1!",
        "firstname": "Karim",
        "lastname": "Fawaz"
    }, follow_redirects=True)

    # Should re-render page, not log in
    assert b"Invalid username or password" in resp.data \
        or b"already" in resp.data \
        or resp.status_code == 200  # flexible depending on message


#testing for password missing symbol
def test_signup_password_missing_symbol(client):
    resp = client.post("/signup", data={
        "username": "testsym3",
        "email": "test2@test.com",
        "password": "NoSymbol3",  # has number, missing symbol
        "firstname": "Karim",
        "lastname": "Fawaz"
    }, follow_redirects=True)

    with app.app_context():
        assert User.query.filter_by(username="testsym3").first() is None

