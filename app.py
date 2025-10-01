# Entry point for the Online Quiz Maker app
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId, InvalidId
from dotenv import load_dotenv

# --- Load .env file ---
load_dotenv()

# --- Flask App ---
app = Flask(__name__)

# Secret Key (from .env or fallback)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

# --- MongoDB Connection ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["quiz_app"]
users_col = db["users"]
quizzes_col = db["quizzes"]

# --- Helpers ---
def current_user():
    if "user_id" in session:
        return {"_id": session["user_id"], "username": session["username"]}
    return None

# --- Auth Routes ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Please provide both username and password.")
            return redirect(url_for("register"))

        if users_col.find_one({"username": username}):
            flash("Username already exists")
            return redirect(url_for("register"))

        users_col.insert_one({
            "username": username,
            "password_hash": generate_password_hash(password)
        })
        flash("Registered successfully. Please login.")
        return redirect(url_for("login"))
    return render_template("register.html", user=current_user())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users_col.find_one({"username": username})
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = str(user["_id"])
            session["username"] = user["username"]
            flash("Login successful")
            return redirect(url_for("index"))
        flash("Invalid credentials")
    return render_template("login.html", user=current_user())


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out")
    return redirect(url_for("index"))

# --- Pages ---
@app.route("/")
def index():
    return render_template("index.html", user=current_user())


@app.route("/quizzes")
def quiz_list():
    quizzes = list(quizzes_col.find().sort("_id", -1))
    return render_template("quiz_list.html", quizzes=quizzes, user=current_user())


@app.route("/create", methods=["GET", "POST"])
def create_quiz():
    # If user not logged in -> redirect to register (as requested)
    if not current_user():
        # Provide a clear flash message and redirect to register page.
        flash("Please register or login before creating a quiz.")
        return redirect(url_for("register"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        questions = request.form.getlist("question")

        if not title or not any(q.strip() for q in questions):
            flash("Title and at least one question required")
            return redirect(url_for("create_quiz"))

        quiz_doc = {
            "title": title,
            "author_id": session["user_id"],
            "author_name": session["username"],
            "questions": []
        }

        for i, qtext in enumerate(questions):
            qtext = qtext.strip()
            if not qtext:
                continue
            choices = request.form.getlist(f"choice-{i}")
            correct = request.form.get(f"correct-{i}")
            # Build choices list; keep order, mark correct by index match
            constructed_choices = []
            for idx, c in enumerate(choices):
                ctext = c.strip()
                if not ctext:
                    continue
                is_corr = (str(idx) == str(correct))
                constructed_choices.append({"text": ctext, "is_correct": is_corr})
            # Only add question if it has at least one choice
            if constructed_choices:
                quiz_doc["questions"].append({
                    "text": qtext,
                    "choices": constructed_choices
                })

        if not quiz_doc["questions"]:
            flash("Each question must have at least one valid choice.")
            return redirect(url_for("create_quiz"))

        quizzes_col.insert_one(quiz_doc)
        flash("Quiz created successfully")
        return redirect(url_for("quiz_list"))

    return render_template("create_quiz.html", user=current_user())


@app.route("/quiz/<quiz_id>")
def take_quiz(quiz_id):
    # safe ObjectId parsing
    try:
        oid = ObjectId(quiz_id)
    except (InvalidId, TypeError):
        flash("Invalid quiz id")
        return redirect(url_for("quiz_list"))

    quiz = quizzes_col.find_one({"_id": oid})
    if not quiz:
        flash("Quiz not found")
        return redirect(url_for("quiz_list"))
    return render_template("take_quiz.html", quiz=quiz, user=current_user())

# --- API Endpoints ---
@app.route("/api/quiz/<quiz_id>/data")
def api_quiz_data(quiz_id):
    try:
        oid = ObjectId(quiz_id)
    except (InvalidId, TypeError):
        return jsonify({"error": "Invalid quiz id"}), 400

    quiz = quizzes_col.find_one({"_id": oid})
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404

    out = []
    for idx, q in enumerate(quiz.get("questions", [])):
        out.append({
            "id": str(idx),
            "text": q.get("text", ""),
            "choices": [{"id": str(i), "text": c.get("text", "")} for i, c in enumerate(q.get("choices", []))]
        })
    return jsonify({"questions": out})


@app.route("/api/quiz/<quiz_id>/submit", methods=["POST"])
def api_quiz_submit(quiz_id):
    try:
        oid = ObjectId(quiz_id)
    except (InvalidId, TypeError):
        return jsonify({"error": "Invalid quiz id"}), 400

    quiz = quizzes_col.find_one({"_id": oid})
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404

    data = request.get_json() or {}
    answers = data.get("answers", {}) or {}

    total = len(quiz.get("questions", []))
    correct_count = 0
    details = []

    for idx, q in enumerate(quiz.get("questions", [])):
        chosen_idx = answers.get(str(idx))
        correct_choice = next((c for c in q.get("choices", []) if c.get("is_correct")), None)
        chosen_choice = None
        if chosen_idx is not None and str(chosen_idx).isdigit():
            ci = int(chosen_idx)
            choices = q.get("choices", [])
            if 0 <= ci < len(choices):
                chosen_choice = choices[ci]

        is_correct = bool(chosen_choice and chosen_choice.get("is_correct"))
        if is_correct:
            correct_count += 1

        details.append({
            "question": q.get("text"),
            "chosen": chosen_choice.get("text") if chosen_choice else None,
            "correct": correct_choice.get("text") if correct_choice else None,
            "is_correct": is_correct
        })

    return jsonify({"score": correct_count, "total": total, "details": details})


# --- Entry Point ---
if __name__ == "__main__":
    # PORT env var used by Render; debug True for dev (disable in production)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
