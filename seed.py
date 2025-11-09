from app import app
from models import db, ConsultForm, ConsultQuestion, FollowupQuestions

with app.app_context():
    # wipe data (order matters because of FKs)
    FollowupQuestions.query.delete()
    ConsultQuestion.query.delete()
    ConsultForm.query.delete()

    # 1) Create the form + primary questions
    derm_form = ConsultForm(name="What is your main concern today?")
    pq_acne  = ConsultQuestion(prompt="Acne/Rosacea",         form=derm_form)
    pq_aging = ConsultQuestion(prompt="Anti-Aging Regimen",   form=derm_form)
    pq_sweat = ConsultQuestion(prompt="Excessive Sweating",   form=derm_form)
    pq_mole  = ConsultQuestion(prompt="Growth/Mole",          form=derm_form)
    pq_hair  = ConsultQuestion(prompt="Hair Loss",            form=derm_form)
    pq_other = ConsultQuestion(prompt="Other?",               form=derm_form)

    db.session.add_all([derm_form, pq_acne, pq_aging, pq_sweat, pq_mole, pq_hair, pq_other])
    db.session.commit()   # IMPORTANT: so pq_* have real IDs

    # 2) Add follow-ups, linked via parent_question_id (or the relationship)
    db.session.add_all([
        # Acne/Rosacea
        FollowupQuestions(prompt="How long have you had these breakouts?",            parent_question_id=pq_acne.id),
        FollowupQuestions(prompt="Current treatments (if any)?",                      parent_question_id=pq_acne.id),

        # Anti-Aging Regimen
        FollowupQuestions(prompt="What products are you using now?",                  parent_question_id=pq_aging.id),
        FollowupQuestions(prompt="Any sensitivities or past irritation?",             parent_question_id=pq_aging.id),

        # Excessive Sweating
        FollowupQuestions(prompt="Which body areas are affected?",                    parent_question_id=pq_sweat.id),
        FollowupQuestions(prompt="How often/how severe is the sweating?",             parent_question_id=pq_sweat.id),

        # Growth/Mole
        FollowupQuestions(prompt="When did you first notice it? Any changes?",         parent_question_id=pq_mole.id),

        # Hair Loss
        FollowupQuestions(prompt="Family history or recent stress/illness/meds?",     parent_question_id=pq_hair.id),
    ])
    db.session.commit()
