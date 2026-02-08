from app import app
from models import db, ConsultForm, ConsultQuestion, FollowupQuestions, User, bcrypt
import os

def run_seed():

    with app.app_context():
    # Only reset DB when you explicitly request it
        RESET_DB = os.getenv("RESET_DB") == "true"

        if RESET_DB:
            print("Dropping and recreating database tables...")
            db.drop_all()

        db.create_all()

        print("Seeding base consultation form + questions...")

    # prevent duplicates if seed runs more than once
        derm_form = ConsultForm.query.filter_by(name="What is your main concern today?").first()
        if not derm_form:
            derm_form = ConsultForm(name="What is your main concern today?")
            db.session.add(derm_form)
            db.session.flush()

            pq_acne  = ConsultQuestion(prompt="Acne/Rosacea",       form=derm_form)
            pq_aging = ConsultQuestion(prompt="Anti-Aging Regimen", form=derm_form)
            pq_sweat = ConsultQuestion(prompt="Excessive Sweating", form=derm_form)
            pq_mole  = ConsultQuestion(prompt="Growth/Mole",        form=derm_form)
            pq_hair  = ConsultQuestion(prompt="Hair Loss",          form=derm_form)
            pq_other = ConsultQuestion(prompt="Other?",             form=derm_form)

            db.session.add_all([pq_acne, pq_aging, pq_sweat, pq_mole, pq_hair, pq_other])
            db.session.flush()

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

        # ---- Admin user from env vars ----
        ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "kadmin")
        ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "kxfawaztest23@gmail.com")
        ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Iam@thehouse3")
        ADMIN_FIRST_NAME = os.getenv("ADMIN_FIRST_NAME", "Karim")
        ADMIN_LAST_NAME = os.getenv("ADMIN_LAST_NAME", "Admin")

        existing = User.query.filter_by(username=ADMIN_USERNAME).first()
        pw_hash = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode("utf-8")

        if existing:
                existing.email = ADMIN_EMAIL
                existing.first_name = ADMIN_FIRST_NAME
                existing.last_name = ADMIN_LAST_NAME
                existing.is_admin = True
                existing.has_medical_history = False
                existing.password_hashed = pw_hash
                print("Admin updated")
        else:
                admin = User(
                    username=ADMIN_USERNAME,
                    email=ADMIN_EMAIL,
                    first_name=ADMIN_FIRST_NAME,
                    last_name=ADMIN_LAST_NAME,
                    password_hashed=pw_hash,
                    is_admin=True,
                    has_medical_history=False
                )
                db.session.add(admin)
                print("Admin created")

        db.session.commit()
        print("Seed completed successfully!")
        
if __name__ == "__main__":
    run_seed()