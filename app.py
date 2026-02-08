from forms import LoginForm, SignupForm
from flask import Flask, render_template, flash, redirect, url_for, session, g, request, jsonify
from flask_debugtoolbar import DebugToolbarExtension
from flask_cors import CORS
from flask_migrate import Migrate
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from models import (
    db,
    connect_db,
    User,
    bcrypt,
    ConsultQuestion,
    ConsultForm,
    ConsultAnswer,
    Consultation,
    FollowupQuestions,
    FollowupAnswers,
)
from sqlalchemy.exc import IntegrityError
from functools import wraps
import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import hashlib

# ------------------------
# ENV
# ------------------------
if os.environ.get("RENDER") is None:
    load_dotenv()

# ------------------------
# APP INIT
# ------------------------
app = Flask(__name__)

# ------------------------
# JWT CONFIG (ORDER MATTERS)
# ------------------------
jwt_key = os.environ.get("JWT_SECRET_KEY")
if not jwt_key:
    raise RuntimeError("JWT_SECRET_KEY is not set")

app.config["JWT_SECRET_KEY"] = jwt_key
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_COOKIE_CSRF_PROTECT"] = False

jwt = JWTManager(app)

# ------------------------
# CORS
# ------------------------
CORS(
    app,
    supports_credentials=True,
    resources={
        r"/api/*": {
            "origins": [
                "https://dermhub-admin-react.onrender.com",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5189",
            ],
            "allow_headers": ["Content-Type", "Authorization"],
            "methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        }
    },
)

# ------------------------
# BASIC CONFIG (NO DUPS)
# ------------------------
database_url = os.environ.get("DATABASE_URL", "postgresql:///dermhubdb").replace(
    "postgres://", "postgresql://", 1
)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = True
app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = False


@app.get("/api/debug/jwt-fingerprint")
def jwt_fingerprint():
    key = app.config["JWT_SECRET_KEY"]
    fp = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return jsonify({"jwt_key_len": len(key), "jwt_key_fp": fp})

# ------------------------
# EXTENSIONS (INIT ONCE)
# ------------------------
connect_db(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)

print("JWT_SECRET_KEY length:", len(app.config["JWT_SECRET_KEY"]))
print("RENDER service:", os.getenv("RENDER_SERVICE_NAME"))

# ------------------------
# AUTH ERROR HANDLERS (API)
# ------------------------
@jwt.unauthorized_loader
def jwt_missing_token(msg):
    return jsonify({"error": "Missing Authorization header"}), 401

@jwt.invalid_token_loader
def jwt_invalid(msg):
    return jsonify({"error": "Invalid token", "detail": msg}), 401

@jwt.expired_token_loader
def jwt_expired(jwt_header, jwt_payload):
    return jsonify({"error": "Token expired"}), 401

# ------------------------
# MAILGUN EMAIL CONFIG
# ------------------------
MAILGUN_DOMAIN  = os.getenv("MAILGUN_DOMAIN")   # Example: sandboxXXXX.mailgun.org
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY") # Starts with key-XXXX

MAILGUN_FROM = f"DermHub <postmaster@{MAILGUN_DOMAIN}>"

MAILGUN_API_BASE = os.getenv("MAILGUN_API_BASE", "https://api.mailgun.net/v3")
MAILGUN_URL  = f"{MAILGUN_API_BASE}/{MAILGUN_DOMAIN}/messages"

if not MAILGUN_DOMAIN or not MAILGUN_API_KEY:
    raise RuntimeError("Missing MAILGUN_DOMAIN or MAILGUN_API_KEY")

print("MAILGUN CONFIG OK:", MAILGUN_DOMAIN, MAILGUN_FROM)

# ------------------------
# FILE UPLOAD LOCATION
# ------------------------
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

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
        auth=HTTPBasicAuth("api", MAILGUN_API_KEY),
        data=data,
        timeout=10,
    )

    return (resp.status_code == 200, resp.text)

# ------------------------
# USER AUTH SESSION HELPERS
# ------------------------
CURR_USER = "curr_user_id"

@app.before_request
def add_user_to_g():
    """Runs before every request. If user is logged in, store user object in g."""
    g.user = User.query.get(session[CURR_USER]) if CURR_USER in session else None

def do_login(user):
    session[CURR_USER] = user.id

def do_logout():
    session.pop(CURR_USER, None)
    flash("You have been logged out!")

def admin_jwt_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user or not getattr(user, "is_admin", False):
            return jsonify({"error": "Forbidden"}), 403
        return fn(*args, **kwargs)
    return wrapper

# ------------------------
# AUTH ROUTES
# ------------------------

@app.route("/", methods=["GET"])
def homepage():
    return redirect(url_for("signup"))

@app.post("/api/admin/login")
def api_admin_login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error":"Missing username/password"}), 400
    user = User.authenticate(username, password)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    if not getattr(user, "is_admin", False):
        return jsonify({"error": "Forbidden"}), 403

    token = create_access_token(identity=str(user.id))
    print("ISSUING token; jwt key len:", len(app.config["JWT_SECRET_KEY"]))
    return jsonify({"access_token": token})

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
    if request.method == "POST":
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"{field}: {err}", "danger")
        return redirect(url_for("signup"))
    return render_template("signup.html", form=form)

@app.route("/admin/signup", methods=["POST"])
@admin_jwt_required
def admin_signup():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error":"username and password are required"}),400
    try:
        user = User.signup(
            username=data["username"],
            email=data.get("email"),
            password=data["password"],
            first_name=data.get("first_name"),
            last_name=data.get("last_name")
        )
        user.is_admin = True
        db.session.commit()
        return jsonify({"message": "Admin created successfully"}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message":"Username or email taken"}), 400

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

@app.errorhandler(401)
def unauthorized(e):
    # Let Flask-JWT-Extended return its own JSON for /api/*
    if request.path.startswith("/api/"):
        return e
    return render_template("401.html"), 401

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

        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join("static/uploads", filename)
            file.save(file_path)

        for q in followup_q:
            answer_val = request.form.get(f"f_answer_{q.id}")
            db.session.add(FollowupAnswers(
                consultation_id=consult.id,
                question_id=q.id,
                text_answer=answer_val,
                file_path=file_path
            ))
        db.session.commit()

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

@app.route("/api/consultations")
@admin_jwt_required
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
@admin_jwt_required
def api_get_consultation_detail(consultation_id):
    c = Consultation.query.get_or_404(consultation_id)

    user = User.query.get(c.user_id)
    primary = ConsultQuestion.query.get(c.primary_question_id)
    initial_answer = c.answers[0].answer_text if c.answers else None

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
@admin_jwt_required
def get_single_question(id):
    q = ConsultQuestion.query.get_or_404(id)
    return jsonify(q.to_dict())

@app.route("/api/questions")
@admin_jwt_required
def get_questions():
    questions = ConsultQuestion.query.all()
    return jsonify([q.to_dict() for q in questions])

@app.route("/api/questions", methods=["POST"])
@admin_jwt_required
def create_questions():
    data = request.json
    q = ConsultQuestion(
        prompt=data["prompt"],
        form_id=data["form_id"]
    )
    db.session.add(q)
    db.session.commit()
    return jsonify(q.to_dict())

@app.route("/api/questions/<int:id>", methods=["PATCH"])
@admin_jwt_required
def update_question(id):
    q = ConsultQuestion.query.get_or_404(id)
    q.prompt = request.json.get("prompt", q.prompt)
    db.session.commit()
    return jsonify(q.to_dict())

@app.route("/api/questions/<int:id>", methods=["DELETE"])
@admin_jwt_required
def delete_question(id):
    q = ConsultQuestion.query.get_or_404(id)

    for f in q.followups:
        FollowupAnswers.query.filter_by(question_id=f.id).delete()
        db.session.delete(f)

    ConsultAnswer.query.filter_by(question_id=q.id).delete()
    Consultation.query.filter_by(primary_question_id=q.id).delete()

    db.session.delete(q)
    db.session.commit()

    return jsonify({"deleted": id})

@app.route("/api/questions/<int:parent_id>/followups", methods=["POST"])
@admin_jwt_required
def create_followupQuestions(parent_id):
    data = request.json
    f = FollowupQuestions(
        prompt=data["prompt"],
        parent_question_id=parent_id
    )
    db.session.add(f)
    db.session.commit()
    return jsonify(f.to_dict())

@app.route("/api/followups/<int:id>", methods=["GET"])
@admin_jwt_required
def get_single_followup(id):
    f = FollowupQuestions.query.get_or_404(id)
    return jsonify(f.to_dict())

@app.route("/api/followups/<int:id>", methods=["PATCH"])
@admin_jwt_required
def update_followup(id):
    f = FollowupQuestions.query.get_or_404(id)
    f.prompt = request.json.get("prompt", f.prompt)
    db.session.commit()
    return jsonify(f.to_dict())

@app.route("/api/followups/<int:id>", methods=["DELETE"])
@admin_jwt_required
def delete_followup(id):
    f = FollowupQuestions.query.get_or_404(id)
    FollowupAnswers.query.filter_by(question_id=id).delete()
    db.session.delete(f)
    db.session.commit()
    return jsonify({"deleted": id})

@app.route('/run-seed')
def run_seed_route():
    from seed import run_seed
    run_seed()
    return "SEED COMPLETE"