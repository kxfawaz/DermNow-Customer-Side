from forms import LoginForm, SignupForm
from flask import Flask, render_template, flash, redirect, url_for, session, g, request
from flask_debugtoolbar import DebugToolbarExtension
from models import db, connect_db, User, bcrypt, ConsultQuestion, ConsultForm, ConsultAnswer, Consultation, FollowupQuestions, FollowupAnswers
import os
from sqlalchemy.exc import IntegrityError
from flask_migrate import Migrate
import requests
from requests.auth import HTTPBasicAuth
from flask import jsonify
from flask_cors import CORS
from functools import wraps
from flask import abort

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:5173", "http://127.0.0.1:5173"])

from dotenv import load_dotenv
load_dotenv()  # Loads MAILGUN + DB credentials from .env file


# ------------------------
# MAILGUN EMAIL CONFIG
# ------------------------

MAILGUN_DOMAIN  = os.getenv("MAILGUN_DOMAIN")   # Example: sandboxXXXX.mailgun.org
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY") # Starts with key-XXXX

# Build the "From:" email line automatically so it never gets stale
MAILGUN_FROM = f"DermHub <postmaster@{MAILGUN_DOMAIN}>"

# Mailgun API endpoint for sending messages
MAILGUN_API_BASE = os.getenv("MAILGUN_API_BASE", "https://api.mailgun.net/v3")
MAILGUN_URL  = f"{MAILGUN_API_BASE}/{MAILGUN_DOMAIN}/messages"

# Crash early if missing credentials (prevents silent failures)
if not MAILGUN_DOMAIN or not MAILGUN_API_KEY:
    raise RuntimeError("Missing MAILGUN_DOMAIN or MAILGUN_API_KEY")

print("MAILGUN CONFIG OK:", MAILGUN_DOMAIN, MAILGUN_FROM)


# ------------------------
# FILE UPLOAD LOCATION
# ------------------------

app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)  # Ensures folder exists


# ------------------------
# DATABASE CONFIG
# ------------------------

database_url = os.environ.get("DATABASE_URL", "postgresql:///dermhubdb")

# Render / Heroku fix: convert deprecated postgres:// → postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = True  # Log SQL to console for debugging
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "GLEYneedsanerf_00")
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False

toolbar = DebugToolbarExtension(app)

connect_db(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)


# ------------------------
# SEND MAIL FUNCTION
# ------------------------

def send_mailgun_email(to_email, subject, text):
    """Send a plain-text email via Mailgun."""
    data = {
        "from": MAILGUN_FROM,
        "to": [to_email],
        "subject": subject,
        "text": text,
    }

    resp = requests.post(
        MAILGUN_URL,
        auth=HTTPBasicAuth("api", MAILGUN_API_KEY),  # Required Mailgun auth
        data=data,
        timeout=10,
    )

    return (resp.status_code == 200, resp.text)  # Returns (success, message)


# ------------------------
# USER AUTH SESSION HELPERS
# ------------------------

CURR_USER = "curr_user_id"

@app.before_request
def add_user_to_g():
    """Runs before every request. If user is logged in, store user object in g."""
    g.user = User.query.get(session[CURR_USER]) if CURR_USER in session else None

def do_login(user):
    session[CURR_USER] = user.id  # Store user ID in session

def do_logout():
    session.pop(CURR_USER, None)  # Remove user from session
    flash("You have been logged out!")




# ------------------------
# AUTH ROUTES
# ------------------------


@app.route("/", methods=["GET"])
def homepage():
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data,
                first_name=form.firstname.data,
                last_name=form.lastname.data,
            )
            db.session.commit()
        except IntegrityError:
            flash("Username or email already taken", "danger")
            return render_template("signup.html", form=form)

        do_login(user)
        return redirect(url_for("dashboard"))
    return render_template("signup.html", form=form)


@app.route("/login", methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.authenticate(form.username.data, form.password.data)
        if user:
            do_login(user)
            return redirect(url_for("dashboard"))
        flash("Invalid login", "danger")
    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    do_logout()
    return redirect(url_for("login"))


@app.route("/admin")
def admin_home():
    return render_template("admin/dashboard.html")

@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


# ------------------------
# MAIN DASHBOARD
# ------------------------

@app.route("/dashboard")
def dashboard():
    if not g.user:
        flash("Please log in first","warning")
        return redirect(url_for("login"))
    latest_form = ConsultForm.query.order_by(ConsultForm.id.desc()).first_or_404()
    return render_template("dashboard.html", latest_form=latest_form)


# ------------------------
# CONSULTATION FLOW
# ------------------------

@app.route("/consult/<int:form_id>", methods=["GET", "POST"])
def consult_form(form_id):
    """Step 1: user selects main concern."""
    form = ConsultForm.query.get_or_404(form_id)

    if request.method == "POST":
        selected_qid = request.form.get("concern")
        if not selected_qid:
            flash("Select one option", "warning")
            return render_template("consult_form.html", form=form)

        # Create consultation record
        consult = Consultation(user_id=g.user.id, form_id=form.id, primary_question_id=int(selected_qid))
        db.session.add(consult)
        db.session.commit()

        return redirect(url_for("consult_followup", consultation_id=consult.id))

    return render_template("consult_form.html", form=form, questions=form.questions)


from werkzeug.utils import secure_filename

@app.route("/consult/<int:consultation_id>/followup", methods=["GET", "POST"])
def consult_followup(consultation_id):
    """Step 2: save follow-up answers and send confirmation email."""
    consult = Consultation.query.get_or_404(consultation_id)
    primary_q = ConsultQuestion.query.get_or_404(consult.primary_question_id)
    followup_q = FollowupQuestions.query.filter_by(parent_question_id=primary_q.id).all()

    if request.method == "POST":
        file = request.files.get("followup-image")
        file_path = None

        # Save uploaded image if present
        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join("static/uploads", filename)
            file.save(file_path)

        # Save responses
        for q in followup_q:
            answer_val = request.form.get(f"f_answer_{q.id}")
            db.session.add(FollowupAnswers(
                consultation_id=consult.id,
                question_id=q.id,
                text_answer=answer_val,
                file_path=file_path
            ))
        db.session.commit()

        # Send confirmation email
        send_mailgun_email(
            to_email=g.user.email,
            subject="DermHub Consultation Complete",
            text="Your consultation has been submitted. Our experts will follow up shortly."
        )

        return redirect(url_for("feedback"))

    return render_template("consult_followup.html", followup_q=followup_q)


@app.route("/feedback")
def feedback():
    return render_template("feedback.html")


### Sending the consultation for primary question to dermhub-admin
@app.route("/api/consultations")
def api_get_consultations():
    consults = Consultation.query.all()
    output = []
    for c in consults:
        primary = ConsultQuestion.query.get(c.primary_question_id)
        output.append({
            "id": c.id,
            "status": c.status,
            "user": c.user_id,
            "primary_question": primary.prompt if primary else None,
            
        })
    return jsonify(output)


@app.route("/api/consultations/<int:consultation_id>")
def api_get_consultation_detail(consultation_id):
    c = Consultation.query.get_or_404(consultation_id)

    #Get user info
    user = User.query.get(c.user_id)

    #Get primary question prompt
    primary = ConsultQuestion.query.get(c.primary_question_id)

    #Get initial answer
    initial_answer = c.answers[0].answer_text if c.answers else None

    #Followup answers
    followups_list = []
    for f in c.followup_answers:
        fq = FollowupQuestions.query.get(f.question_id)
        followups_list.append({
            "prompt": fq.prompt if fq else None,
            "text_answer": f.text_answer,
            "file_path": f.file_path
        })

    return jsonify({
        "id": c.id,
        "status": c.status,
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name
        } if user else None,
        "primary_concern": primary.prompt if primary else None,
        "initial_answer": initial_answer,
        "followup_answers": followups_list

    })

@app.route("/api/questions/<int:id>", methods=["GET"])
def get_single_question(id):
    q = ConsultQuestion.query.get_or_404(id)
    return jsonify(q.to_dict())

@app.route("/api/questions")  #Route to the api that lists all questions for admin to change it
def get_questions():
    questions = ConsultQuestion.query.all()
    return jsonify([q.to_dict() for q in questions])


@app.route("/api/questions", methods=["POST"]) ## Route that sends a POST request to create a main question
def create_questions():
    data = request.json
    q = ConsultQuestion(
        prompt=data["prompt"],
        form_id=data["form_id"]
        )
    db.session.add(q)
    db.session.commit()

    return jsonify(q.to_dict())

@app.route("/api/questions/<int:id>", methods=["PATCH"]) ## Route that updates/edits main questions
def update_question(id):
    q = ConsultQuestion.query.get_or_404(id)
    q.prompt = request.json.get("prompt", q.prompt)

    db.session.commit()
    return jsonify(q.to_dict())


@app.route("/api/questions/<int:id>", methods=["DELETE"])
def delete_question(id):
    q = ConsultQuestion.query.get_or_404(id)

    # Delete followup answers for each followup question
    for f in q.followups:
        FollowupAnswers.query.filter_by(question_id=f.id).delete()
        db.session.delete(f)   # delete the followup question itself

    #  Delete consult answers that reference this main question
    ConsultAnswer.query.filter_by(question_id=q.id).delete()

    #  Delete consultations that use this as their primary_question
    Consultation.query.filter_by(primary_question_id=q.id).delete()

    # delete the main question
    db.session.delete(q)
    db.session.commit()

    return jsonify({"deleted": id})


@app.route("/api/questions/<int:parent_id>/followups", methods=["POST"]) ##Route to create a followup question
def create_followupQuestions(parent_id):
    data = request.json
    f = FollowupQuestions(
        prompt = data["prompt"],
        parent_question_id = parent_id
    )
    db.session.add(f)
    db.session.commit()
    return jsonify(f.to_dict())


@app.route("/api/followups/<int:id>", methods=["GET"])
def get_single_followup(id):
    f = FollowupQuestions.query.get_or_404(id)
    return jsonify(f.to_dict())


@app.route("/api/followups/<int:id>", methods=["PATCH"]) ## Route that updates/edits main questions
def update_followup(id):
    f = FollowupQuestions.query.get_or_404(id)
    f.prompt = request.json.get("prompt", f.prompt)

    db.session.commit()
    return jsonify(f.to_dict())


@app.route("/api/followups/<int:id>", methods=["DELETE"])  ## Delete followup questions
def delete_followup(id):
    f = FollowupQuestions.query.get_or_404(id)
    FollowupAnswers.query.filter_by(question_id=id).delete()

    db.session.delete(f)
    db.session.commit()

    return jsonify({"deleted": id})

