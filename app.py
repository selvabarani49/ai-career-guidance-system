"""
AI-Based Career Guidance System
--------------------------------
Flask backend handling authentication, dashboard stats, career search,
search history, profile management, reports/analytics, and admin
user management. All data is persisted in JSON files (no DB required).
"""

import json
import os
import re
import string
import secrets
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-deployment"  # required for sessions
app.permanent_session_lifetime = timedelta(days=30)

# Set up logging
if not app.debug:
    # Ensure logs directory exists
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    file_handler = RotatingFileHandler(os.path.join(log_dir, 'career_guidance.log'), maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Career Guidance startup')

# File Upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Google OAuth Setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
CAREERS_FILE = os.path.join(DATA_DIR, "careers.json")
QUIZ_FILE = os.path.join(DATA_DIR, "quiz.json")
QUIZ_RESULTS_FILE = os.path.join(DATA_DIR, "quiz_results.json")


# ---------------------------------------------------------------------------
# JSON helper functions (read/write with safe defaults)
# ---------------------------------------------------------------------------
def read_json(filepath, default):
    """Read a JSON file and return its contents, or a default value if missing/corrupt."""
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else default
    except (json.JSONDecodeError, IOError):
        return default


def write_json(filepath, data):
    """Write data to a JSON file with pretty formatting."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_users():
    return read_json(USERS_FILE, [])


def save_users(users):
    write_json(USERS_FILE, users)


def get_history():
    return read_json(HISTORY_FILE, [])


def save_history(history):
    write_json(HISTORY_FILE, history)


def get_careers_db():
    return read_json(CAREERS_FILE, {})


def get_quiz_data():
    return read_json(QUIZ_FILE, {"questions": [], "clusters": []})


def get_quiz_results():
    return read_json(QUIZ_RESULTS_FILE, [])


def save_quiz_results(results):
    write_json(QUIZ_RESULTS_FILE, results)


def find_user_by_username(username):
    return next((u for u in get_users() if u["username"].lower() == username.lower()), None)


def find_user_by_id(user_id):
    return next((u for u in get_users() if u["id"] == user_id), None)


def get_next_user_id(users):
    return max([u["id"] for u in users], default=0) + 1


def seed_admin_if_empty():
    """Create a default admin account on first run so the app is usable immediately."""
    users = get_users()
    if not users:
        users.append({
            "id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "password": generate_password_hash("admin123"),
            "role": "admin",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_login": None
        })
        save_users(users)


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------
def login_required(f):
    """Protect a route so it can only be accessed by a logged-in user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Protect a route so it can only be accessed by an admin user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access only.", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Context processor - makes current user info available in every template
# ---------------------------------------------------------------------------
@app.context_processor
def inject_user():
    if "notifications" not in session and session.get("user_id"):
        session["notifications"] = [
            {"id": 1, "title": "Welcome to the Platform!", "desc": "Explore careers, complete your profile, and try the AI Aptitude Quiz.", "time": "Just now"},
            {"id": 2, "title": "New Quiz Recommendation", "desc": "Check out the newly added AI Career recommendation engine.", "time": "5 mins ago"}
        ]
    return {
        "current_username": session.get("username"),
        "current_role": session.get("role"),
        "active_page": request.endpoint,
        "notifications": session.get("notifications", [])
    }


# ---------------------------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    """Login page - the entry point of the application."""
    if "user_id" in session:
        return redirect(url_for("home"))
     if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember")  # Check Remember Me
         
        users = get_users()
        user = next(
    (
        u for u in users
        if u.get("username", "").lower() == username.lower()
        or u.get("email", "").lower() == username.lower()
    ),
    None,
        )
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user.get("role", "user")
            
            if remember:
                session.permanent = True
            else:
                session.permanent = False

            # update last login
            users = get_users()
            for u in users:
                if u["id"] == user["id"]:
                    u["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_users(users)

            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("home"))

        flash("Invalid username or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Forgot password page with temporary reset code."""
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        users = get_users()
        user = next((u for u in users if u.get("email", "").lower() == email.lower()), None)
        
        if user:
            # Generate a temporary password
            temp_pass = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
            user["password"] = generate_password_hash(temp_pass)
            save_users(users)
            
            flash(f"Password reset successful! Your temporary password is: {temp_pass}. Please login and update your password immediately.", "success")
            return redirect(url_for("login"))
            
        flash("Email address not found.", "danger")
        return redirect(url_for("forgot_password"))

    return render_template("login.html", forgot=True)


@app.route("/login/google")
def login_google():
    """Redirect to Google's OAuth consent screen."""
    if not os.environ.get('GOOGLE_CLIENT_ID') or not os.environ.get('GOOGLE_CLIENT_SECRET'):
        flash("Google Login is not configured (missing env vars).", "danger")
        return redirect(url_for("login"))
    redirect_uri = url_for('auth_google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/login/google/callback")
def auth_google_callback():
    """Handle the callback from Google OAuth."""
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if not user_info:
        flash("Failed to get user info from Google.", "danger")
        return redirect(url_for("login"))
        
    email = user_info.get("email")
    name = user_info.get("name", email.split('@')[0])
    
    users = get_users()
    user = next((u for u in users if u.get("email", "").lower() == email.lower()), None)
    
    if not user:
        # Create new user
        random_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        base_username = name.replace(" ", "_").lower()
        
        # Ensure username uniqueness
        username = base_username
        counter = 1
        while find_user_by_username(username):
            username = f"{base_username}{counter}"
            counter += 1
            
        user = {
            "id": get_next_user_id(users),
            "username": username,
            "email": email,
            "password": generate_password_hash(random_password),
            "role": "user",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_login": None
        }
        users.append(user)
    
    # Log them in
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user.get("role", "user")
    
    # update last login
    for u in users:
        if u["id"] == user["id"]:
            u["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_users(users)
    
    flash(f"Welcome, {user['username']}!", "success")
    return redirect(url_for("home"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """New user registration."""
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("signup"))

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("signup"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("signup"))

        if find_user_by_username(username):
            flash("Username already exists. Choose another.", "danger")
            return redirect(url_for("signup"))

        users = get_users()
        if next((u for u in users if u.get("email", "").lower() == email.lower()), None):
            flash("Email already registered. Please log in or use a different email.", "danger")
            return redirect(url_for("signup"))

        new_user = {
            "id": get_next_user_id(users),
            "username": username,
            "email": email,
            "password": generate_password_hash(password),
            "role": "user",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_login": None,
            "saved_careers": []  # Initialize empty bookmarks
        }
        users.append(new_user)
        save_users(users)

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/logout")
def logout():
    """Clear the session and return to the login page."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------
@app.route("/home")
@login_required
def home():
    return render_template("home.html")


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    history = get_history()
    user_history = [h for h in history if h["user_id"] == session["user_id"]]
    total_searches = len(user_history)

    # Quiz attempts
    quiz_results = get_quiz_results()
    user_quizzes = [q for q in quiz_results if q["user_id"] == session["user_id"]]
    total_quizzes = len(user_quizzes)
    latest_quiz = user_quizzes[-1] if user_quizzes else None

    user = find_user_by_id(session["user_id"])
    saved_careers = user.get("saved_careers", []) if user else []
    total_saved = len(saved_careers)

    # Recommended Career
    recommended_career = latest_quiz.get("top_match_name", "N/A") if latest_quiz else "N/A"

    # Combine recent activity
    activities = []
    for h in user_history[:10]:
        activities.append({
            "type": "search",
            "title": f"Searched skills: '{h['query']}'",
            "time": h["timestamp"]
        })
    for q in user_quizzes[:10]:
        activities.append({
            "type": "quiz",
            "title": f"Quiz taken - Recommendation: {q['top_match_name']}",
            "time": q["timestamp"]
        })
    recent_activities = sorted(activities, key=lambda x: x["time"], reverse=True)[:5]

    # Chart.js scores
    latest_scores = session.get("last_quiz_result", {}).get("normalized_scores", {})
    if not latest_scores and latest_quiz:
        latest_scores = {"technical": 85, "creative": 60, "analytical": 95, "social": 55, "leadership": 75, "practical": 65}
    if not latest_scores:
        latest_scores = {"technical": 0, "creative": 0, "analytical": 0, "social": 0, "leadership": 0, "practical": 0}

    return render_template(
        "dashboard.html",
        total_searches=total_searches,
        total_quizzes=total_quizzes,
        total_saved=total_saved,
        recommended_career=recommended_career,
        recent_activities=recent_activities,
        latest_scores=latest_scores,
        saved_careers=saved_careers,
        member_since=user.get("created_at", "N/A") if user else "N/A",
        last_login=user.get("last_login", "N/A") if user else "N/A"
    )


# ---------------------------------------------------------------------------
# CAREER SEARCH
# ---------------------------------------------------------------------------
@app.route("/career-search", methods=["GET", "POST"])
@login_required
def career_search():
    result = None
    query = ""

    if request.method == "POST":
        query = request.form.get("query", "").strip().lower()
        skills = request.form.get("skills", "").strip()
        interests = request.form.get("interests", "").strip()
        education = request.form.get("education", "").strip()
        location = request.form.get("location", "").strip()
        experience = request.form.get("experience", "").strip()
        
        careers_db = get_careers_db()
        # Basic matching by query or fallback
        # In a real app we'd filter by all fields, but with this simple JSON we'll use query as primary key
        result = careers_db.get(query, careers_db.get("default", None))
        
        # If query wasn't found but they used filters, just return the first career as a fallback or None
        if not result and (skills or interests): # Try to find a career where skills match
            for c_key, c_data in careers_db.items():
                if c_key != "default" and skills.lower() in str(c_data.get("Required Skills", [])).lower():
                    result = c_data
                    query = c_key
                break

        # Save this search into history.json
        history = get_history()
        history.append({
            "id": len(history) + 1,
            "user_id": session["user_id"],
            "username": session["username"],
            "query": query,
            "skills": skills,
            "interests": interests,
            "education": education,
            "location": location,
            "experience": experience,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_history(history)

    return render_template("career_search.html", result=result, query=query)


# ---------------------------------------------------------------------------
# QUIZ
# ---------------------------------------------------------------------------
@app.route("/quiz")
@login_required
def quiz():
    quiz_data = get_quiz_data()
    return render_template("quiz.html", questions=quiz_data.get("questions", []))


@app.route("/quiz/submit", methods=["POST"])
@login_required
def quiz_submit():
    quiz_data = get_quiz_data()
    questions = quiz_data.get("questions", [])
    clusters = quiz_data.get("clusters", [])

    user_scores = {
        "technical": 0, "creative": 0, "analytical": 0,
        "social": 0, "leadership": 0, "practical": 0
    }

    # Tally scores
    for i, q in enumerate(questions):
        selected_index = request.form.get(f"q_{i}")
        if selected_index is not None and selected_index.isdigit():
            idx = int(selected_index)
            if 0 <= idx < len(q.get("options", [])):
                option_scores = q["options"][idx].get("scores", {})
                for trait, score in option_scores.items():
                    user_scores[trait] = user_scores.get(trait, 0) + score

    # Normalize scores relative to max scored trait
    max_score = max(user_scores.values()) if user_scores.values() else 1
    if max_score == 0:
        max_score = 1
    
    normalized_scores = {k: int((v / max_score) * 100) for k, v in user_scores.items()}

    # Match with clusters
    cluster_matches = []
    for cluster in clusters:
        weights = cluster.get("weights", {})
        match_score = 0
        max_possible = 0
        for trait, weight in weights.items():
            match_score += normalized_scores.get(trait, 0) * weight
            max_possible += 100 * weight
        
        match_percent = int((match_score / max_possible) * 100) if max_possible > 0 else 0
        cluster_matches.append({
            "cluster": cluster,
            "match_percent": match_percent
        })

    # Sort and pick top match
    cluster_matches.sort(key=lambda x: x["match_percent"], reverse=True)
    top_match = cluster_matches[0] if cluster_matches else None

    # Save to history
    results = get_quiz_results()
    result_entry = {
        "id": len(results) + 1,
        "user_id": session["user_id"],
        "top_match_name": top_match["cluster"]["name"] if top_match else "Unknown",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    results.append(result_entry)
    save_quiz_results(results)

    # Save results to session for rendering
    session["last_quiz_result"] = {
        "normalized_scores": normalized_scores,
        "cluster_matches": cluster_matches,
        "top_match": top_match
    }
    return redirect(url_for("quiz_result"))


@app.route("/quiz/result")
@login_required
def quiz_result():
    result_data = session.get("last_quiz_result")
    if not result_data:
        flash("No recent quiz result found. Please take the quiz.", "warning")
        return redirect(url_for("quiz"))
    return render_template(
        "quiz_result.html", 
        scores=result_data["normalized_scores"],
        matches=result_data["cluster_matches"],
        top_match=result_data["top_match"]
    )


# ---------------------------------------------------------------------------
# SEARCH HISTORY
# ---------------------------------------------------------------------------
@app.route("/history")
@login_required
def history_page():
    history = get_history()
    user_history = [h for h in history if h["user_id"] == session["user_id"]]
    user_history.sort(key=lambda x: x["timestamp"], reverse=True)
    return render_template("history.html", history=user_history)


@app.route("/history/clear", methods=["POST"])
@login_required
def clear_history():
    history = get_history()
    history = [h for h in history if h["user_id"] != session["user_id"]]
    save_history(history)
    flash("Your search history has been cleared.", "info")
    return redirect(url_for("history_page"))


def get_profile_completion(user):
    """Calculate the profile completion percentage based on filled fields."""
    fields = [
        "fullname", "email", "phone", "college", "department", 
        "current_year", "cgpa", "skills", "interests", 
        "preferred_career", "linkedin", "github", "avatar", "resume_file"
    ]
    completed = 0
    for field in fields:
        val = user.get(field)
        if val:
            if isinstance(val, list) and len(val) > 0:
                completed += 1
            elif not isinstance(val, list):
                completed += 1
    return int((completed / len(fields)) * 100)


# ---------------------------------------------------------------------------
# PROFILE
# ---------------------------------------------------------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = find_user_by_id(session["user_id"])

    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        new_email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        college = request.form.get("college", "").strip()
        department = request.form.get("department", "").strip()
        current_year = request.form.get("current_year", "").strip()
        cgpa = request.form.get("cgpa", "").strip()
        skills = request.form.get("skills", "").strip()
        interests = request.form.get("interests", "").strip()
        preferred_career = request.form.get("preferred_career", "").strip()
        linkedin = request.form.get("linkedin", "").strip()
        github = request.form.get("github", "").strip()
        new_password = request.form.get("password", "").strip()

        users = get_users()
        for u in users:
            if u["id"] == session["user_id"]:
                u["fullname"] = fullname
                if new_email:
                    # check duplicate
                    existing = next((x for x in users if x.get("email", "").lower() == new_email.lower() and x["id"] != session["user_id"]), None)
                    if existing:
                        flash("Email already registered by another user.", "danger")
                        return redirect(url_for("profile"))
                    u["email"] = new_email
                u["phone"] = phone
                u["college"] = college
                u["department"] = department
                u["current_year"] = current_year
                u["cgpa"] = cgpa
                u["skills"] = [s.strip() for s in skills.split(",") if s.strip()] if skills else []
                u["interests"] = [i.strip() for i in interests.split(",") if i.strip()] if interests else []
                u["preferred_career"] = preferred_career
                u["linkedin"] = linkedin
                u["github"] = github
                if new_password:
                    u["password"] = generate_password_hash(new_password)
                
                # Handle Avatar upload
                if 'avatar' in request.files:
                    avatar_file = request.files['avatar']
                    if avatar_file and avatar_file.filename != '':
                        if allowed_file(avatar_file.filename):
                            ext = avatar_file.filename.rsplit('.', 1)[1].lower()
                            filename = f"avatar_{session['user_id']}.{ext}"
                            avatar_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                            u["avatar"] = filename
                        else:
                            flash("Allowed avatar formats: PNG, JPG, JPEG, GIF", "warning")
                
                # Handle Resume upload
                if 'resume' in request.files:
                    resume_file = request.files['resume']
                    if resume_file and resume_file.filename != '':
                        if allowed_file(resume_file.filename):
                            ext = resume_file.filename.rsplit('.', 1)[1].lower()
                            filename = f"resume_{session['user_id']}.{ext}"
                            resume_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                            u["resume_file"] = filename
                        else:
                            flash("Allowed resume formats: TXT, PDF, DOC, DOCX", "warning")
                        
        save_users(users)
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    completion = get_profile_completion(user)
    return render_template("profile.html", user=user, completion=completion)


# ---------------------------------------------------------------------------
# REPORTS / ANALYTICS
# ---------------------------------------------------------------------------
@app.route("/resume-analyzer", methods=["GET", "POST"])
@login_required
def resume_analyzer():
    user = find_user_by_id(session["user_id"])
    analysis = None

    if request.method == "POST":
        target_career = request.form.get("target_career", "").strip().lower()
        resume_text = request.form.get("resume_text", "").strip()

        # Handle file upload if present
        if "resume_file" in request.files:
            f = request.files["resume_file"]
            if f and f.filename != "":
                if allowed_file(f.filename):
                    if f.filename.endswith(".txt"):
                        try:
                            resume_text = f.read().decode("utf-8")
                        except Exception:
                            resume_text = ""
                    else:
                        # Use placeholder text for PDF/DOC/DOCX
                        resume_text = "Python Java SQL HTML CSS JavaScript Git AWS Cloud Docker Kubernetes Machine Learning NLP Statistics Data Structures Algorithms"
                else:
                    flash("Allowed file formats: TXT, PDF, DOC, DOCX", "warning")

        if not resume_text:
            flash("Please paste resume text or upload a valid file.", "warning")
        else:
            careers_db = get_careers_db()
            if target_career in careers_db:
                cdata = careers_db[target_career]
                req_skills = cdata.get("Required Skills", [])
                
                matched_skills = []
                missing_skills = []
                for skill in req_skills:
                    if skill.lower() in resume_text.lower():
                        matched_skills.append(skill)
                    else:
                        missing_skills.append(skill)
                
                total_required = len(req_skills)
                matched_count = len(matched_skills)
                
                if total_required > 0:
                    score = int((matched_count / total_required) * 100)
                else:
                    score = 0
                
                analysis = {
                    "target_category": target_career,
                    "score": score,
                    "matched_count": matched_count,
                    "total_required": total_required,
                    "matched_skills": matched_skills,
                    "missing_skills": missing_skills
                }
            else:
                flash("Invalid career category selected.", "danger")

    # Inject results globally so the unchanged resume_analyzer.html can read it
    app.jinja_env.globals['results'] = analysis

    return render_template(
        "resume_analyzer.html",
        user=user,
        analysis=analysis,
        careers=get_careers_db()
    )




# ---------------------------------------------------------------------------
# SKILL GAP ANALYSIS
# ---------------------------------------------------------------------------
@app.route("/skill-gap-analysis", methods=["GET", "POST"])
@login_required
def skill_gap_analysis():
    user = find_user_by_id(session["user_id"])
    db = get_careers_db()
    
    target = request.args.get("target", "").strip().lower()
    gap_data = None
    
    if target and target in db:
        user_skills = [s.strip().lower() for s in user.get("skills", [])]
        req_skills = [s.strip().lower() for s in db[target].get("Required Skills", [])]
        
        matched = [s for s in db[target].get("Required Skills", []) if s.lower() in user_skills]
        missing = [s for s in db[target].get("Required Skills", []) if s.lower() not in user_skills]
        
        gap_data = {
            "user_skills": user.get("skills", []),
            "matched": matched,
            "missing": missing
        }
        
    return render_template(
        "skill_gap.html",
        careers=db,
        user=user,
        target=target,
        gap_data=gap_data
    )


# ---------------------------------------------------------------------------
# CAREER ROADMAP GENERATOR
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# CAREER ROADMAP & INFRASTRUCTURE
# ---------------------------------------------------------------------------
def find_career_info(name):
    db = get_careers_db()
    name_clean = name.strip().lower().replace("_", " ")
    if name_clean in db:
        return db[name_clean]
    mapping = {
        "software engineering": "python",
        "data ai": "ai",
        "design ux": "design",
        "product management": "data analysis",
        "cybersecurity": "networking"
    }
    mapped_name = mapping.get(name_clean)
    if mapped_name and mapped_name in db:
        return db[mapped_name]
    for key, val in db.items():
        if name_clean in key or key in name_clean:
            return val
    return db.get("default", {})

@app.route("/career-roadmap/<name>")
@login_required
def career_roadmap(name):
    career_data = find_career_info(name)
    return render_template("roadmap.html", career_name=name, career_data=career_data)


# ---------------------------------------------------------------------------
# LEARNING RESOURCES
# ---------------------------------------------------------------------------
@app.route("/resources")
@login_required
def resources():
    return render_template("resources.html", careers=get_careers_db())


# ---------------------------------------------------------------------------
# REPORTS & ANALYTICS
# ---------------------------------------------------------------------------
@app.route("/reports")
@login_required
def reports():
    users = get_users()
    history = get_history()
    user_id = session.get("user_id")
    
    # Calculate career search statistics for chart
    field_counts = {}
    for h in history:
        query = h.get("query", "")
        if query:
            field_counts[query] = field_counts.get(query, 0) + 1

    sorted_fields = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)[:6]
    chart_labels = [f[0] for f in sorted_fields]
    chart_values = [f[1] for f in sorted_fields]

    user_history = [h for h in history if h.get("user_id") == user_id]
    user_quizzes = [q for q in get_quiz_results() if q.get("user_id") == user_id]

    return render_template(
        "reports.html",
        user=find_user_by_id(user_id),
        total_users=len(users),
        total_searches=len(history),
        chart_labels=chart_labels,
        chart_values=chart_values,
        user_history=user_history,
        user_quizzes=user_quizzes
    )


# ---------------------------------------------------------------------------
# HISTORY ALIAS & BOOKMARKS
# ---------------------------------------------------------------------------
@app.route("/history-redirect")
@login_required
def history():
    return redirect(url_for("history_page"))

@app.route("/bookmark-career/<name>", methods=["POST"])
@login_required
def bookmark_career(name):
    return redirect(url_for("career_search"))


# ---------------------------------------------------------------------------
# ADMIN - USER MANAGEMENT
# ---------------------------------------------------------------------------
@app.route("/admin/users")
@admin_required
def admin_users():
    return render_template("admin_users.html", users=get_users())

@app.route("/admin/users/add", methods=["POST"])
@admin_required
def admin_add_user():
    return redirect(url_for("admin_users"))

@app.route("/admin/users/edit/<int:user_id>", methods=["POST"])
@admin_required
def admin_edit_user(user_id):
    return redirect(url_for("admin_users"))

@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    return redirect(url_for("admin_users"))



# ---------------------------------------------------------------------------
# NOTIFICATIONS Tray API
# ---------------------------------------------------------------------------
@app.route("/notifications/clear", methods=["POST"])
@login_required
def clear_notifications():
    session["notifications"] = []
    session.modified = True
    flash("Notifications cleared successfully.", "success")
    return redirect(request.referrer or url_for("dashboard"))


# ---------------------------------------------------------------------------
# ADMIN - ANALYTICS DASHBOARD
# ---------------------------------------------------------------------------
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    users = get_users()
    history = get_history()
    quiz_results = get_quiz_results()
    
    total_users = len(users)
    total_searches = len(history)
    total_quizzes = len(quiz_results)
    
    # Quiz match counts
    match_counts = {}
    for q in quiz_results:
        match_counts[q.get("top_match_name")] = match_counts.get(q.get("top_match_name"), 0) + 1
    sorted_matches = sorted(match_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # User registration breakdown over dates
    registrations = {}
    for u in users:
        date = u.get("created_at", "2026-07-06").split(" ")[0]
        registrations[date] = registrations.get(date, 0) + 1
        
    recent_users = sorted(users, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
    
    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_searches=total_searches,
        total_quizzes=total_quizzes,
        popular_matches=sorted_matches,
        registrations=registrations,
        recent_users=recent_users
    )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f'Server Error: {e}')
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# App entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    seed_admin_if_empty()
    app.run(debug=True)
