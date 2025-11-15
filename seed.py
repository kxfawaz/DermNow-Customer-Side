from app import app
from models import db, ConsultForm, ConsultQuestion, FollowupQuestions

with app.app_context():

    print("📌 Dropping and recreating database tables...")

    db.drop_all()
    db.create_all()   # ✅ IMPORTANT: Create tables before seeding

    print("🌱 Seeding base consultation form + questions...")

    derm_form = ConsultForm(name="What is your main concern today?")
    pq_acne  = ConsultQuestion(prompt="Acne/Rosacea",         form=derm_form)
    pq_aging = ConsultQuestion(prompt="Anti-Aging Regimen",   form=derm_form)
    pq_sweat = ConsultQuestion(prompt="Excessive Sweating",   form=derm_form)
    pq_mole  = ConsultQuestion(prompt="Growth/Mole",          form=derm_form)
    pq_hair  = ConsultQuestion(prompt="Hair Loss",            form=derm_form)
    pq_other = ConsultQuestion(prompt="Other?",               form=derm_form)

    db.session.add_all([derm_form, pq_acne, pq_aging, pq_sweat, pq_mole, pq_hair, pq_other])
    db.session.commit()

    db.session.add_all([
        FollowupQuestions(prompt="How long have you had these breakouts?",        parent_question_id=pq_acne.id),
        FollowupQuestions(prompt="Current treatments (if any)?",                  parent_question_id=pq_acne.id),

        FollowupQuestions(prompt="What products are you using now?",              parent_question_id=pq_aging.id),
        FollowupQuestions(prompt="Any sensitivities or past irritation?",         parent_question_id=pq_aging.id),

        FollowupQuestions(prompt="Which body areas are affected?",                parent_question_id=pq_sweat.id),
        FollowupQuestions(prompt="How often/how severe is the sweating?",         parent_question_id=pq_sweat.id),

        FollowupQuestions(prompt="When did you first notice it? Any changes?",    parent_question_id=pq_mole.id),

        FollowupQuestions(prompt="Family history or recent stress/illness/meds?", parent_question_id=pq_hair.id),
    ])
    db.session.commit()

    print("✅ Seed completed successfully!")
