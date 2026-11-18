import os
import random
import secrets
import string
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from flask import Flask, jsonify, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.mysql import INTEGER
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:@127.0.0.1:3306/personality_passwords",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


def get_cipher():
    key = os.getenv("PASSWORD_FERNET_KEY")
    if not key:
        raise RuntimeError("PASSWORD_FERNET_KEY is required")
    return Fernet(key.encode())


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(INTEGER(unsigned=True), primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    passwords = db.relationship("SavedPassword", backref="user", cascade="all, delete-orphan")


class SavedPassword(db.Model):
    __tablename__ = "saved_passwords"
    id = db.Column(INTEGER(unsigned=True), primary_key=True)
    user_id = db.Column(INTEGER(unsigned=True), db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    encrypted_password = db.Column(db.LargeBinary, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_password_name"),)


class UserProfile(db.Model):
    __tablename__ = "user_profiles"
    id = db.Column(INTEGER(unsigned=True), primary_key=True)
    user_id = db.Column(INTEGER(unsigned=True), db.ForeignKey("users.id"), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    place_of_birth = db.Column(db.String(160), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    answers = db.Column(db.JSON, nullable=False)
    user = db.relationship("User", backref=db.backref("profile", uselist=False, cascade="all, delete-orphan"))


QUESTIONS = [
    {"id": 1, "text": "Which setting helps you relax most?", "options": ["Ocean", "Forest", "City", "Library"]},
    {"id": 2, "text": "Choose a favorite color.", "options": ["Blue", "Red", "Green", "Purple"]},
    {"id": 3, "text": "Which animal do you feel closest to?", "options": ["Lion", "Eagle", "Dolphin", "Fox"]},
    {"id": 4, "text": "Pick a comfortable season.", "options": ["Spring", "Summer", "Autumn", "Winter"]},
    {"id": 5, "text": "Which activity gives you energy?", "options": ["Music", "Exercise", "Reading", "Gaming"]},
    {"id": 6, "text": "Choose a meal type.", "options": ["Sweet", "Spicy", "Savory", "Fresh"]},
    {"id": 7, "text": "Which type of movie do you prefer?", "options": ["Comedy", "Drama", "Adventure", "Mystery"]},
    {"id": 8, "text": "Pick a dream destination.", "options": ["Mountain", "Beach", "Museum", "Countryside"]},
    {"id": 9, "text": "Which sound do you enjoy?", "options": ["Rain", "Music", "Silence", "Birdsong"]},
    {"id": 10, "text": "Choose a hobby.", "options": ["Painting", "Cooking", "Traveling", "Programming"]},
    {"id": 11, "text": "How do you prefer to learn?", "options": ["Watching", "Listening", "Reading", "Doing"]},
    {"id": 12, "text": "Pick a morning drink.", "options": ["Coffee", "Tea", "Juice", "Water"]},
    {"id": 13, "text": "Choose a natural element.", "options": ["Fire", "Earth", "Air", "Water"]},
    {"id": 14, "text": "Which shape do you prefer?", "options": ["Circle", "Square", "Triangle", "Star"]},
    {"id": 15, "text": "Pick a personality strength.", "options": ["Creative", "Calm", "Bold", "Reliable"]},
    {"id": 16, "text": "Choose a type of book.", "options": ["Fantasy", "Biography", "Science", "Poetry"]},
    {"id": 17, "text": "Which time of day suits you?", "options": ["Dawn", "Morning", "Afternoon", "Night"]},
    {"id": 18, "text": "Pick a sport.", "options": ["Swimming", "Cycling", "Running", "Football"]},
    {"id": 19, "text": "Which flower do you like?", "options": ["Rose", "Sunflower", "Lily", "Lavender"]},
    {"id": 20, "text": "Choose a transport style.", "options": ["Car", "Train", "Bicycle", "Plane"]},
]

# Repeated options and varied identifiers are intentional: the quiz only needs a stable,
# memorable personalization pool for version 0.1.
EXTRA_WORDS = [
    ("Moon", ["Silver", "Bright", "Distant", "Quiet"]),
    ("River", ["Deep", "Swift", "Clear", "Calm"]),
    ("Garden", ["Bloom", "Green", "Wild", "Peaceful"]),
    ("Cloud", ["Soft", "White", "Storm", "High"]),
    ("Stone", ["Strong", "Smooth", "Ancient", "Warm"]),
]
for index in range(21, 51):
    word, options = EXTRA_WORDS[(index - 21) % len(EXTRA_WORDS)]
    QUESTIONS.append({
        "id": index,
        "text": f"Which word describes {word.lower()} for you?",
        "options": options,
    })

PASSWORD_QUESTIONS = [
    {"id": 101, "text": "How long should the password be?", "options": ["12 characters", "16 characters", "20 characters", "24 characters"]},
    {"id": 102, "text": "Which character mix do you want?", "options": ["Letters and digits", "Mixed case and digits", "Mixed case, digits and symbols", "Maximum variety"]},
    {"id": 103, "text": "Which theme should influence the password?", "options": ["Ocean", "Forest", "Space", "Music", "Fantasy", "Technology"]},
    {"id": 104, "text": "What style should the password use?", "options": ["Short memorable words", "Rhyming phrases", "Sentence-like", "Unexpected compounds"]},
    {"id": 105, "text": "How difficult should it be to guess?", "options": ["Strong", "Very strong", "Extreme"]},
    {"id": 106, "text": "Should it be easy to type?", "options": ["Yes, simple symbols", "Yes, no ambiguous characters", "No preference"]},
    {"id": 107, "text": "What should it resemble?", "options": ["A phrase", "A name", "A place", "A playful object"]},
    {"id": 108, "text": "Choose a mood.", "options": ["Calm", "Energetic", "Mysterious", "Cheerful"]},
    {"id": 109, "text": "Choose a writing style.", "options": ["Proper capitalization", "All lowercase", "Alternating case", "Random case"]},
    {"id": 110, "text": "Choose an optional symbol style.", "options": ["Common symbols", "Minimal symbols", "No symbols", "AI choice"]},
]


def current_user_id():
    return session.get("user_id")


def validate_password(password):
    if len(password) < 12:
        return "Password must contain at least 12 characters."
    if not any(char.isupper() for char in password):
        return "Password must contain an uppercase letter."
    if not any(char.islower() for char in password):
        return "Password must contain a lowercase letter."
    if not any(char.isdigit() for char in password):
        return "Password must contain a digit."
    if not any(char in "!@#$%&*" for char in password):
        return "Password must contain a special character."
    return None


def generate_ai_password(profile, constraint_answers, password_name):
    api_url = os.getenv("AI_API_URL")
    api_key = os.getenv("AI_API_KEY")
    model = os.getenv("AI_MODEL")
    if not api_url or not api_key or not model:
        raise RuntimeError("AI_API_URL, AI_API_KEY, and AI_MODEL must be configured")

    payload = {
        "name": profile.name,
        "dateOfBirth": profile.date_of_birth.isoformat(),
        "placeOfBirth": profile.place_of_birth,
        "profileAnswers": profile.answers,
        "timeOfCreation": datetime.now(timezone.utc).isoformat(),
        "passwordName": password_name,
        "constraints": constraint_answers,
    }
    prompt = (
        "Create one memorable, human-like password from the JSON data. "
        "Honor every length and character constraint; use the personality and theme naturally. "
        "It must be difficult to decode and must not reuse personal values verbatim. "
        "Return only the password, no labels or explanation.\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You generate secure, memorable passwords. Never return prose."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 100,
    }).encode("utf-8")
    request_object = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request_object, timeout=30) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("AI provider returned HTTP %s: %s" % (exc.code, details[:300])) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach the AI provider: %s" % exc.reason) from exc

    choices = response_body.get("choices") or []
    if not choices:
        raise RuntimeError("AI provider returned no password choices")
    message = choices[0].get("message") or {}
    password = message.get("content")
    if password is None:
        password = message.get("reasoning_content") or choices[0].get("text") or ""
    password = str(password).strip()
    password = password.strip("\"'`").replace("\n", "").replace(" ", "")
    if password.startswith("```"):
        password = password.split("```")[-1].strip()
    if not password:
        raise RuntimeError("AI provider returned an empty password")
    return password


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    name = str(data.get("name", "")).strip()
    date_of_birth = str(data.get("dateOfBirth", "")).strip()
    place_of_birth = str(data.get("placeOfBirth", "")).strip()
    answers = data.get("answers")
    if len(username) < 3 or len(password) < 8:
        return jsonify(error="Username must have 3 characters and password 8 characters."), 400
    if not name or not date_of_birth or not place_of_birth:
        return jsonify(error="Name, date of birth, and place of birth are required."), 400
    if not isinstance(answers, dict) or len(answers) != 10:
        return jsonify(error="Complete all 10 account personality questions."), 400
    try:
        parsed_birth = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
    except ValueError:
        return jsonify(error="Date of birth must use YYYY-MM-DD format."), 400
    if User.query.filter_by(username=username).first():
        return jsonify(error="Username already exists."), 409
    user = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.flush()
    profile = UserProfile(
        user_id=user.id,
        name=name,
        date_of_birth=parsed_birth,
        place_of_birth=place_of_birth,
        answers={str(key): str(value) for key, value in answers.items()},
    )
    db.session.add(profile)
    db.session.commit()
    session["user_id"] = user.id
    return jsonify(username=user.username)


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(username=str(data.get("username", "")).strip()).first()
    if not user or not check_password_hash(user.password_hash, str(data.get("password", ""))):
        return jsonify(error="Invalid username or password."), 401
    session["user_id"] = user.id
    return jsonify(username=user.username)


@app.post("/api/logout")
def logout():
    session.pop("user_id", None)
    return jsonify(ok=True)


@app.get("/api/session")
def session_status():
    user_id = current_user_id()
    if not user_id:
        return jsonify(authenticated=False)
    user = db.session.get(User, user_id)
    return jsonify(authenticated=True, username=user.username if user else None)


@app.get("/api/questions")
def questions():
    kind = request.args.get("kind", "password")
    if kind != "account" and not current_user_id():
        return jsonify(error="Login required."), 401
    seed = secrets.randbits(32)
    rng = random.Random(seed)
    pool = QUESTIONS if kind == "account" else PASSWORD_QUESTIONS
    selected = rng.sample(pool, 10)
    for question in selected:
        copied = dict(question)
        copied["options"] = list(question["options"])
        rng.shuffle(copied["options"])
        selected[selected.index(question)] = copied
    return jsonify(seed=seed, questions=selected)


@app.post("/api/generate")
def generate():
    user_id = current_user_id()
    if not user_id:
        return jsonify(error="Login required."), 401
    data = request.get_json(silent=True) or {}
    answers = data.get("answers")
    name = str(data.get("name", "")).strip()
    if not isinstance(answers, dict) or len(answers) != 10:
        return jsonify(error="All 10 questions must be answered."), 400
    if not name:
        return jsonify(error="Password name is required."), 400

    profile = db.session.execute(
        db.select(UserProfile).where(UserProfile.user_id == user_id)
    ).scalar_one_or_none()
    if not profile:
        return jsonify(error="Complete account creation before generating passwords."), 400

    constraint_answers = {str(key): str(value) for key, value in answers.items()}
    try:
        password = generate_ai_password(profile, constraint_answers, name)
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503

    constraint_error = validate_password(password)
    length_answer = constraint_answers.get("101", "")
    requested_length = 12
    for candidate in (24, 20, 16, 12):
        if str(candidate) in length_answer:
            requested_length = candidate
            break
    if len(password) != requested_length:
        constraint_error = "AI result did not meet the requested password length."

    symbol_answer = constraint_answers.get("110", "")
    if "No symbols" in symbol_answer and any(char in "!@#$%&*" for char in password):
        constraint_error = "AI result did not honor the no-symbol constraint."

    mixed_answer = constraint_answers.get("102", "")
    if "digits" in mixed_answer.lower() and not any(char.isdigit() for char in password):
        constraint_error = "AI result did not include the requested digits."
    if "Mixed case" in mixed_answer and not (
        any(char.isupper() for char in password) and any(char.islower() for char in password)
    ):
        constraint_error = "AI result did not include the requested mixed case."
    if constraint_error:
        return jsonify(error=constraint_error), 400

    if SavedPassword.query.filter_by(user_id=user_id, name=name).first():
        return jsonify(error="A password with that name already exists."), 409
    encrypted = get_cipher().encrypt(password.encode())
    saved = SavedPassword(user_id=user_id, name=name, encrypted_password=encrypted)
    db.session.add(saved)
    db.session.commit()
    return jsonify(name=name, password=password)


@app.get("/api/passwords")
def list_passwords():
    user_id = current_user_id()
    if not user_id:
        return jsonify(error="Login required."), 401
    cipher = get_cipher()
    result = []
    for item in SavedPassword.query.filter_by(user_id=user_id).order_by(SavedPassword.name).all():
        try:
            password = cipher.decrypt(item.encrypted_password).decode()
        except (InvalidToken, UnicodeDecodeError):
            password = "[unable to decrypt]"
        result.append({"name": item.name, "password": password})
    return jsonify(passwords=result)


@app.post("/api/passwords/<name>/update")
def update_password(name):
    user_id = current_user_id()
    if not user_id:
        return jsonify(error="Login required."), 401
    data = request.get_json(silent=True) or {}
    password = str(data.get("password", ""))
    constraint_error = validate_password(password)
    if constraint_error:
        return jsonify(error=constraint_error), 400
    item = SavedPassword.query.filter_by(user_id=user_id, name=name).first()
    if not item:
        return jsonify(error="Password not found."), 404
    item.encrypted_password = get_cipher().encrypt(password.encode())
    db.session.commit()
    return jsonify(name=name, password=password)


@app.delete("/api/passwords/<name>")
def delete_password(name):
    user_id = current_user_id()
    if not user_id:
        return jsonify(error="Login required."), 401
    item = SavedPassword.query.filter_by(user_id=user_id, name=name).first()
    if not item:
        return jsonify(error="Password not found."), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify(ok=True)


@app.get("/api/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", database="connected")
    except Exception as exc:
        return jsonify(status="error", database=str(exc)), 503


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
