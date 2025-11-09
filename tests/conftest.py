import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app import app, db
from models import User, ConsultForm, ConsultQuestion, FollowupQuestions

@pytest.fixture
def client():
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql:///dermhub_test"
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.drop_all()
        db.create_all()

        # Create a consult form (name is REQUIRED)
        form = ConsultForm(name="Test Dermatology Form")
        db.session.add(form)
        db.session.flush()

        # Primary question
        q1 = ConsultQuestion(prompt="Acne", form_id=form.id)
        db.session.add(q1)
        db.session.flush()

        # Follow-up question linked to primary question
        f1 = FollowupQuestions(prompt="How long has this been a concern?", parent_question_id=q1.id)
        db.session.add(f1)

        db.session.commit()

    with app.test_client() as client:
        yield client
