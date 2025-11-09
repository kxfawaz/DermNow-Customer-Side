from models import Consultation, FollowupAnswers, User, db
from app import app

def login(client):
    with app.app_context():   # ✅ create user inside context
        u = User.signup("u1", "u1@test.com", "password", "A", "B")
        db.session.commit()
    client.post("/login", data={"username": "u1", "password": "password"})
    return u

def test_select_primary_question(client):
    login(client)

    client.post("/consult/1", data={"concern": "1"})

    with app.app_context():   # ✅ query inside context
        consult = Consultation.query.first()
        assert consult is not None
        assert consult.primary_question_id == 1

def test_followup_answers(client):
    login(client)
    client.post("/consult/1", data={"concern": "1"})

    with app.app_context():
        consult = Consultation.query.first()

    client.post(f"/consult/{consult.id}/followup", data={
        "f_answer_1": "More than 6 months"
    })

    with app.app_context():  # ✅ query inside context
        answers = FollowupAnswers.query.all()
        assert len(answers) == 1
        assert answers[0].text_answer == "More than 6 months"
