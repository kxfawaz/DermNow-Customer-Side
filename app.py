# load environment variables if not on Render
if os.environ.get("RENDER") is None:
    load_dotenv()

# create Flask app
app = Flask(__name__)

# get JWT secret key from environment
jwt_key = os.environ.get("JWT_SECRET_KEY")
if not jwt_key:
    raise RuntimeError("JWT_SECRET_KEY is not set")

# configure JWT
app.config["JWT_SECRET_KEY"] = jwt_key
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_COOKIE_CSRF_PROTECT"] = False

# initialize JWT
jwt = JWTManager(app)

# configure CORS for frontend access
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

# configure database
database_url = os.environ.get("DATABASE_URL", "postgresql:///dermhubdb").replace(
    "postgres://", "postgresql://", 1
)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# initialize database and bcrypt
connect_db(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)

# JWT error handler if token missing
@jwt.unauthorized_loader
def jwt_missing_token(msg):
    return jsonify({"error": "Missing Authorization header"}), 401

# JWT error handler if token invalid
@jwt.invalid_token_loader
def jwt_invalid(msg):
    return jsonify({"error": "Invalid token", "detail": msg}), 401

# JWT error handler if token expired
@jwt.expired_token_loader
def jwt_expired(jwt_header, jwt_payload):
    return jsonify({"error": "Token expired"}), 401

# custom decorator to require admin JWT
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

# admin login route
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
    return jsonify({"access_token": token})

# create new admin
@app.route("/api/admin/signup", methods=["POST"])
@admin_jwt_required
def admin_signup():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    try:
        user = User.signup(
            username=username,
            email=data.get("email"),
            password=password,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
        )
        user.is_admin = True
        db.session.commit()
        return jsonify({"message": "Admin created successfully"}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Username or email taken"}), 400

# return all consultations
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
            "user": f"{c.user.first_name}{c.user.last_name}" if c.user else None,
            "primary_question": primary.prompt if primary else None,
        })
    return jsonify(output)

# return single consultation detail
@app.route("/api/consultations/<int:consultation_id>")
@admin_jwt_required
def api_get_consultation_detail(consultation_id):
    c = Consultation.query.get_or_404(consultation_id)

    user = User.query.get(c.user_id)
    primary = ConsultQuestion.query.get(c.primary_question_id)

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
        "followup_answers": followups_list
    })