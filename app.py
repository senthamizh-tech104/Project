"""
SkillSphere AI - AI-Powered Learning & Skill Development Platform
Engineered by Team Code Ninja
"""

import json
import os
import random
import string
import sqlite3
from datetime import date, datetime
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    MySQLError = Exception

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "skillsphere.db"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "skillsphere-super-secret-key-2026")

# ---------------------------------------------------------------------------
# Gemini setup
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
gemini_model = None
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        print("Gemini setup failed:", e)
        gemini_model = None


def ask_gemini(prompt):
    """Send a prompt to Gemini and return plain text. Returns None on failure."""
    if not gemini_model:
        return None
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print("Gemini error:", e)
        return None


# ---------------------------------------------------------------------------
# Database Engine & Connection Handling
# ---------------------------------------------------------------------------
USE_MYSQL = os.getenv("USE_MYSQL", "false").lower() in ("true", "1", "yes")


def get_db():
    """Return a database connection (MySQL or SQLite) with connection info."""
    if USE_MYSQL and MYSQL_AVAILABLE:
        try:
            conn = mysql.connector.connect(
                host=os.getenv("MYSQL_HOST", "localhost"),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "skillsphere"),
                connection_timeout=2
            )
            return conn, "mysql"
        except Exception as e:
            print("MySQL connection failed, falling back to SQLite:", e)
    
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"


def run_query(query, params=None, fetch=False, fetchone=False, commit=False):
    """Run a SQL query across SQLite or MySQL seamlessly."""
    conn_obj = get_db()
    if not conn_obj:
        return None
    conn, engine = conn_obj
    result = None
    try:
        if engine == "mysql":
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            if commit:
                conn.commit()
                result = cursor.lastrowid
            elif fetchone:
                result = cursor.fetchone()
            elif fetch:
                result = cursor.fetchall()
            cursor.close()
        else:
            sqlite_query = query.replace("%s", "?")
            cursor = conn.cursor()
            cursor.execute(sqlite_query, params or ())
            if commit:
                conn.commit()
                result = cursor.lastrowid
            elif fetchone:
                row = cursor.fetchone()
                result = dict(row) if row else None
            elif fetch:
                rows = cursor.fetchall()
                result = [dict(r) for r in rows]
            cursor.close()
    except Exception as e:
        print(f"Database query error [{engine}]:", e)
        result = None
    finally:
        conn.close()
    return result


def init_database():
    """Initialize database tables and seed sample data if tables don't exist."""
    conn_obj = get_db()
    if not conn_obj:
        return
    conn, engine = conn_obj
    cursor = conn.cursor()

    if engine == "sqlite":
        schema_statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Learner',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                type TEXT DEFAULT 'Video',
                duration TEXT DEFAULT '1 week',
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                progress INTEGER DEFAULT 0,
                enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER,
                score INTEGER DEFAULT 0,
                taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                certificate_id TEXT NOT NULL UNIQUE,
                date DATE NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS discussions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_gamification (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                xp INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 1,
                level INTEGER DEFAULT 1,
                last_active DATE,
                badges TEXT DEFAULT '["Welcome Explorer"]',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS mock_interviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                score INTEGER DEFAULT 0,
                feedback TEXT,
                strengths TEXT,
                improvements TEXT,
                ideal_answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS roadmaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                target_role TEXT NOT NULL,
                milestones_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS code_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                code_snippet TEXT NOT NULL,
                ai_review TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        ]
        for stmt in schema_statements:
            cursor.execute(stmt)
        conn.commit()
    conn.close()

    seed_initial_data()


def get_gamification(user_id):
    """Retrieve or initialize gamification stats for user."""
    g = run_query("SELECT * FROM user_gamification WHERE user_id = %s", (user_id,), fetchone=True)
    if not g:
        run_query(
            "INSERT INTO user_gamification (user_id, xp, streak, level, last_active, badges) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, 100, 1, 1, date.today(), json.dumps(["Welcome Explorer"])),
            commit=True,
        )
        g = run_query("SELECT * FROM user_gamification WHERE user_id = %s", (user_id,), fetchone=True)
    
    if g and isinstance(g.get("badges"), str):
        try:
            g["badges_list"] = json.loads(g["badges"])
        except Exception:
            g["badges_list"] = ["Welcome Explorer"]
    else:
        g["badges_list"] = ["Welcome Explorer"]
    return g


def award_xp(user_id, amount, reason=None, badge=None):
    """Award XP, calculate level up, add badge if unlocked."""
    g = get_gamification(user_id)
    if not g:
        return None

    current_xp = g.get("xp", 0) + amount
    new_level = max(1, (current_xp // 250) + 1)
    badges = g.get("badges_list", ["Welcome Explorer"])

    if badge and badge not in badges:
        badges.append(badge)

    if current_xp >= 300 and "XP Pioneer" not in badges:
        badges.append("XP Pioneer")
    if current_xp >= 750 and "Code Samurai" not in badges:
        badges.append("Code Samurai")
    if current_xp >= 1200 and "Grandmaster" not in badges:
        badges.append("Grandmaster")

    run_query(
        "UPDATE user_gamification SET xp = %s, level = %s, badges = %s, last_active = %s WHERE user_id = %s",
        (current_xp, new_level, json.dumps(badges), date.today(), user_id),
        commit=True,
    )
    return {"xp": current_xp, "level": new_level, "badges": badges}


def seed_initial_data():
    """Seed initial courses, demo users, skills, and enrollments."""
    user_count = run_query("SELECT COUNT(*) AS c FROM users", fetchone=True)
    if not user_count or user_count.get("c", 0) == 0:
        demo_password_hash = generate_password_hash("password123")
        
        # 1. Learner (Alex Morgan)
        learner_id = run_query(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            ("Alex Morgan", "learner@skillsphere.ai", demo_password_hash, "Learner"),
            commit=True,
        )
        
        # 2. Trainer (Sarah Jenkins)
        trainer_id = run_query(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            ("Sarah Jenkins", "trainer@skillsphere.ai", demo_password_hash, "Trainer"),
            commit=True,
        )
        
        # 3. Admin (David Kim)
        admin_id = run_query(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            ("David Kim", "admin@skillsphere.ai", demo_password_hash, "Admin"),
            commit=True,
        )

        sample_courses = [
            ("Python for Beginners", "Learn Python programming from scratch with hands-on exercises and real-world projects.", "Video", "2 weeks", trainer_id),
            ("SQL Fundamentals", "Master database queries, relational design, joins, indexing, and data normalization.", "Video", "10 days", trainer_id),
            ("Machine Learning Basics", "Introduction to supervised and unsupervised learning, regression, classification, and neural nets.", "Video", "3 weeks", trainer_id),
            ("Cloud Computing 101", "Understand cloud architecture, AWS & Google Cloud services, serverless deployment, and scaling.", "PDF", "1 week", admin_id),
            ("Data Structures & Algorithms", "Core CS concepts: arrays, linked lists, trees, graphs, dynamic programming for technical interviews.", "Assignment", "4 weeks", trainer_id),
            ("AI Ethics & Governance", "Responsible AI development, safety frameworks, fairness metrics, and corporate deployment practices.", "PDF", "5 days", admin_id),
        ]
        
        course_ids = []
        for title, desc, ctype, duration, created_by in sample_courses:
            cid = run_query(
                "INSERT INTO courses (title, description, type, duration, created_by) VALUES (%s, %s, %s, %s, %s)",
                (title, desc, ctype, duration, created_by),
                commit=True,
            )
            course_ids.append(cid)

        # Seed Learner skills
        learner_skills = [("Python", 85), ("SQL", 72), ("AI & ML", 65), ("Cloud", 55), ("Algorithms", 70)]
        for sname, score in learner_skills:
            run_query(
                "INSERT INTO skills (user_id, name, score) VALUES (%s, %s, %s)",
                (learner_id, sname, score),
                commit=True,
            )

        # Seed Trainer skills
        trainer_skills = [("Python", 95), ("SQL", 92), ("AI & ML", 90), ("Cloud", 88), ("Pedagogy", 94)]
        for sname, score in trainer_skills:
            run_query(
                "INSERT INTO skills (user_id, name, score) VALUES (%s, %s, %s)",
                (trainer_id, sname, score),
                commit=True,
            )

        # Seed Learner Enrollments
        if len(course_ids) >= 3:
            run_query(
                "INSERT INTO enrollments (user_id, course_id, progress) VALUES (%s, %s, %s)",
                (learner_id, course_ids[0], 85), commit=True
            )
            run_query(
                "INSERT INTO enrollments (user_id, course_id, progress) VALUES (%s, %s, %s)",
                (learner_id, course_ids[1], 100), commit=True
            )
            run_query(
                "INSERT INTO enrollments (user_id, course_id, progress) VALUES (%s, %s, %s)",
                (learner_id, course_ids[2], 40), commit=True
            )

            cert_code = "SSA-SQL" + "".join(random.choices(string.digits, k=4))
            run_query(
                "INSERT INTO certificates (user_id, course_id, certificate_id, date) VALUES (%s, %s, %s, %s)",
                (learner_id, course_ids[1], cert_code, date.today()), commit=True
            )

        run_query(
            "INSERT INTO assessments (user_id, course_id, score) VALUES (%s, %s, %s)",
            (learner_id, course_ids[0] if course_ids else 1, 4), commit=True
        )

        run_query(
            "INSERT INTO user_gamification (user_id, xp, streak, level, last_active, badges) VALUES (%s, %s, %s, %s, %s, %s)",
            (learner_id, 480, 5, 2, date.today(), json.dumps(["Welcome Explorer", "Python Pioneer", "Quiz Whiz"])),
            commit=True
        )
        run_query(
            "INSERT INTO user_gamification (user_id, xp, streak, level, last_active, badges) VALUES (%s, %s, %s, %s, %s, %s)",
            (trainer_id, 1450, 14, 6, date.today(), json.dumps(["Master Mentor", "Code Samurai", "Course Architect", "7-Day Streak"])),
            commit=True
        )
        run_query(
            "INSERT INTO user_gamification (user_id, xp, streak, level, last_active, badges) VALUES (%s, %s, %s, %s, %s, %s)",
            (admin_id, 980, 9, 4, date.today(), json.dumps(["Platform Guardian", "Quiz Whiz", "Cloud Navigator"])),
            commit=True
        )

        run_query(
            "INSERT INTO discussions (user_id, title, content) VALUES (%s, %s, %s)",
            (learner_id, "Tips for mastering Python list comprehensions and generators?",
             "I have been working through the Python course and finding generator expressions super clean. What are your favorite patterns?"),
            commit=True
        )
        run_query(
            "INSERT INTO discussions (user_id, title, content) VALUES (%s, %s, %s)",
            (trainer_id, "Welcome to the SkillSphere AI Community Hub!",
             "Feel free to ask questions, share insights, and discuss courses. We are excited to support your learning journey."),
            commit=True
        )


init_database()


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("You are not authorized to perform this action.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


DEFAULT_SKILLS = ["Python", "SQL", "AI", "Cloud"]


def seed_default_skills(user_id):
    for name in DEFAULT_SKILLS:
        run_query(
            "INSERT INTO skills (user_id, name, score) VALUES (%s, %s, %s)",
            (user_id, name, random.randint(40, 75)),
            commit=True,
        )


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "Learner")

        if not name or not email or not password:
            flash("All fields are required. Please fill in name, email, and password.", "danger")
            return redirect(url_for("register"))

        existing = run_query(
            "SELECT id FROM users WHERE email = %s", (email,), fetchone=True
        )
        if existing:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for("login"))

        hashed = generate_password_hash(password)
        user_id = run_query(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (name, email, hashed, role),
            commit=True,
        )
        if user_id is None:
            flash("Could not create account due to a database error. Please try again.", "danger")
            return redirect(url_for("register"))

        seed_default_skills(user_id)
        award_xp(user_id, 100, "Account Creation", "Welcome Explorer")

        session["user_id"] = user_id
        session["name"] = name
        session["role"] = role
        flash(f"Welcome to SkillSphere AI, {name}! Your account is ready with +100 XP.", "success")
        return redirect(url_for("dashboard"))

    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = run_query(
            "SELECT * FROM users WHERE email = %s", (email,), fetchone=True
        )
        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password. You can also use the 1-click Demo Login below.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("auth.html", mode="login")


@app.route("/demo-login/<role>")
def demo_login(role):
    role_normalized = role.lower().strip()
    role_map = {
        "learner": "learner@skillsphere.ai",
        "trainer": "trainer@skillsphere.ai",
        "admin": "admin@skillsphere.ai",
    }
    
    if role_normalized == "guest":
        guest_email = "guest@skillsphere.ai"
        user = run_query("SELECT * FROM users WHERE email = %s", (guest_email,), fetchone=True)
        if not user:
            hashed = generate_password_hash("guest123")
            uid = run_query(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ("Guest Learner", guest_email, hashed, "Learner"),
                commit=True
            )
            seed_default_skills(uid)
            award_xp(uid, 100, "Guest Access")
            user = run_query("SELECT * FROM users WHERE id = %s", (uid,), fetchone=True)
        
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        flash("Instant Demo Access: Logged in as Guest Learner.", "success")
        return redirect(url_for("dashboard"))

    email = role_map.get(role_normalized)
    if not email:
        flash("Invalid demo role selected.", "danger")
        return redirect(url_for("login"))

    user = run_query("SELECT * FROM users WHERE email = %s", (email,), fetchone=True)
    if not user:
        init_database()
        user = run_query("SELECT * FROM users WHERE email = %s", (email,), fetchone=True)

    if user:
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        flash(f"Quick Login: Logged in as {user['name']} ({user['role']}).", "success")
        return redirect(url_for("dashboard"))

    flash("Demo account not found. Please try again.", "danger")
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Context processor for global template variables
# ---------------------------------------------------------------------------
@app.context_processor
def inject_gamification():
    if "user_id" in session:
        g = get_gamification(session["user_id"])
        return {
            "user_xp": g.get("xp", 0) if g else 0,
            "user_streak": g.get("streak", 1) if g else 1,
            "user_level": g.get("level", 1) if g else 1,
            "user_badges": g.get("badges_list", []) if g else [],
        }
    return {}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]

    active_courses = run_query(
        "SELECT COUNT(*) AS c FROM enrollments WHERE user_id = %s AND progress < 100",
        (user_id,), fetchone=True,
    ) or {"c": 0}

    certificates = run_query(
        "SELECT COUNT(*) AS c FROM certificates WHERE user_id = %s",
        (user_id,), fetchone=True,
    ) or {"c": 0}

    skills = run_query(
        "SELECT name, score FROM skills WHERE user_id = %s", (user_id,), fetch=True
    ) or []
    avg_score = round(sum(s["score"] for s in skills) / len(skills)) if skills else 0

    enrollments = run_query(
        """SELECT e.progress, e.course_id, c.title, c.type, c.duration FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           WHERE e.user_id = %s ORDER BY e.enrolled_at DESC LIMIT 6""",
        (user_id,), fetch=True,
    ) or []

    overall_progress = (
        round(sum(e["progress"] for e in enrollments) / len(enrollments))
        if enrollments else 0
    )

    assessments = run_query(
        "SELECT score, taken_at FROM assessments WHERE user_id = %s ORDER BY taken_at DESC LIMIT 5",
        (user_id,), fetch=True,
    ) or []

    gamification = get_gamification(user_id)

    return render_template(
        "dashboard.html",
        active_courses=active_courses.get("c", 0),
        certificates=certificates.get("c", 0),
        skill_score=avg_score,
        overall_progress=overall_progress,
        skills=skills,
        enrollments=enrollments,
        assessments=assessments,
        gamification=gamification,
    )


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------
@app.route("/courses")
@login_required
def courses():
    all_courses = run_query("SELECT * FROM courses ORDER BY created_at DESC", fetch=True) or []
    my_enrollments = run_query(
        "SELECT course_id, progress FROM enrollments WHERE user_id = %s",
        (session["user_id"],), fetch=True,
    ) or []
    enrolled_ids = {e["course_id"]: e["progress"] for e in my_enrollments}
    return render_template("courses.html", courses=all_courses, enrolled_ids=enrolled_ids)


@app.route("/course/create", methods=["POST"])
@roles_required("Admin", "Trainer")
def course_create():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    ctype = request.form.get("type", "Video")
    duration = request.form.get("duration", "1 week")

    if not title:
        flash("Course title is required.", "danger")
        return redirect(url_for("courses"))

    run_query(
        "INSERT INTO courses (title, description, type, duration, created_by) VALUES (%s, %s, %s, %s, %s)",
        (title, description, ctype, duration, session["user_id"]),
        commit=True,
    )
    award_xp(session["user_id"], 50, "Course Published", "Course Creator")
    flash("Course created successfully! (+50 XP)", "success")
    return redirect(url_for("courses"))


@app.route("/course/delete/<int:course_id>", methods=["POST"])
@roles_required("Admin", "Trainer")
def course_delete(course_id):
    course = run_query("SELECT id FROM courses WHERE id = %s", (course_id,), fetchone=True)
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("courses"))

    run_query("DELETE FROM courses WHERE id = %s", (course_id,), commit=True)
    flash("Course deleted.", "info")
    return redirect(url_for("courses"))


@app.route("/course/enroll/<int:course_id>", methods=["POST"])
@login_required
def course_enroll(course_id):
    course = run_query("SELECT id FROM courses WHERE id = %s", (course_id,), fetchone=True)
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("courses"))

    already = run_query(
        "SELECT id FROM enrollments WHERE user_id = %s AND course_id = %s",
        (session["user_id"], course_id), fetchone=True,
    )
    if already:
        flash("You are already enrolled in this course.", "info")
    else:
        run_query(
            "INSERT INTO enrollments (user_id, course_id, progress) VALUES (%s, %s, 0)",
            (session["user_id"], course_id), commit=True,
        )
        award_xp(session["user_id"], 25, "Course Enrolled")
        flash("Enrolled successfully! Ready to start learning. (+25 XP)", "success")
    return redirect(url_for("learn", course_id=course_id))


@app.route("/learn/<int:course_id>")
@login_required
def learn(course_id):
    course = run_query("SELECT * FROM courses WHERE id = %s", (course_id,), fetchone=True)
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("courses"))

    enrollment = run_query(
        "SELECT * FROM enrollments WHERE user_id = %s AND course_id = %s",
        (session["user_id"], course_id), fetchone=True,
    )
    if not enrollment:
        run_query(
            "INSERT INTO enrollments (user_id, course_id, progress) VALUES (%s, %s, 0)",
            (session["user_id"], course_id), commit=True,
        )
        enrollment = {"progress": 0}

    return render_template("learning.html", course=course, enrollment=enrollment)


@app.route("/learn/<int:course_id>/complete", methods=["POST"])
@login_required
def learn_complete(course_id):
    run_query(
        "UPDATE enrollments SET progress = 100 WHERE user_id = %s AND course_id = %s",
        (session["user_id"], course_id), commit=True,
    )

    existing_cert = run_query(
        "SELECT id FROM certificates WHERE user_id = %s AND course_id = %s",
        (session["user_id"], course_id), fetchone=True,
    )
    if not existing_cert:
        cert_id = "SSA-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        run_query(
            "INSERT INTO certificates (user_id, course_id, certificate_id, date) VALUES (%s, %s, %s, %s)",
            (session["user_id"], course_id, cert_id, date.today()), commit=True,
        )
        award_xp(session["user_id"], 150, "Course Completed", "Certified Specialist")
        flash("🎉 Congratulations! Course completed, certificate issued! (+150 XP)", "success")
    else:
        award_xp(session["user_id"], 50, "Course Review")
        flash("Course marked as 100% complete.", "success")

    return redirect(url_for("learn", course_id=course_id))


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------
QUIZ_QUESTIONS = [
    {
        "question": "Which keyword is used to define a function in Python?",
        "options": ["func", "def", "function", "lambda"],
        "answer": "def",
    },
    {
        "question": "Which SQL clause is used to filter rows?",
        "options": ["ORDER BY", "GROUP BY", "WHERE", "SELECT"],
        "answer": "WHERE",
    },
    {
        "question": "Which of these is a supervised learning algorithm?",
        "options": ["K-Means", "Linear Regression", "PCA", "Apriori"],
        "answer": "Linear Regression",
    },
    {
        "question": "What does 'API' stand for?",
        "options": [
            "Application Programming Interface",
            "Automated Program Instruction",
            "Application Process Integration",
            "Advanced Programming Index",
        ],
        "answer": "Application Programming Interface",
    },
    {
        "question": "Which cloud service model provides raw virtual machines?",
        "options": ["SaaS", "PaaS", "IaaS", "FaaS"],
        "answer": "IaaS",
    },
]


@app.route("/assessment", methods=["GET", "POST"])
@login_required
def assessment():
    if request.method == "POST":
        score = 0
        for i, q in enumerate(QUIZ_QUESTIONS):
            selected = request.form.get(f"q{i}")
            if selected == q["answer"]:
                score += 1

        percentage = round((score / len(QUIZ_QUESTIONS)) * 100)
        result = "Passed" if percentage >= 50 else "Failed"

        run_query(
            "INSERT INTO assessments (user_id, score) VALUES (%s, %s)",
            (session["user_id"], score), commit=True,
        )

        if result == "Passed":
            award_xp(session["user_id"], 60, "Quiz Passed", "Quiz Whiz")
            flash("Quiz Passed! You earned +60 XP!", "success")

        return render_template(
            "assessment.html",
            questions=QUIZ_QUESTIONS,
            submitted=True,
            score=score,
            total=len(QUIZ_QUESTIONS),
            percentage=percentage,
            result=result,
        )

    return render_template("assessment.html", questions=QUIZ_QUESTIONS, submitted=False)


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------
@app.route("/skills")
@login_required
def skills():
    user_skills = run_query(
        "SELECT name, score FROM skills WHERE user_id = %s", (session["user_id"],), fetch=True
    ) or []
    return render_template("skills.html", skills=user_skills)


@app.route("/skills/analyze", methods=["POST"])
@login_required
def skills_analyze():
    data = request.get_json(silent=True) or {}
    current_skills = data.get("current_skills", "").strip()
    required_skills = data.get("required_skills", "").strip()

    if not current_skills or not required_skills:
        return jsonify({"error": "Please provide both current and required skills."}), 400

    prompt = f"""You are a skill gap analysis assistant for a learning platform.
Current skills of the learner: {current_skills}
Required skills for the target role: {required_skills}

Respond ONLY in plain text using exactly this structure (no markdown symbols):
Missing Skills: <comma separated list>
Recommended Courses: <comma separated list>
Learning Path: <short numbered plan in 3-5 steps, separated by semicolons>
"""

    reply = ask_gemini(prompt)
    if reply is None:
        return jsonify({
            "fallback": True,
            "missing_skills": f"Skills needed for {required_skills}: System Architecture, Advanced Workflows, CI/CD, Containerization",
            "recommended_courses": "Python for Beginners, SQL Fundamentals, Machine Learning Basics, Cloud Computing 101",
            "learning_path": "1. Master core fundamentals; 2. Build hands-on portfolio projects; 3. Take assessment quizzes; 4. Earn verified course certificates.",
        })

    missing, recommended, path = "Not specified", "Not specified", "Not specified"
    for line in reply.splitlines():
        line = line.strip()
        if line.lower().startswith("missing skills"):
            missing = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("recommended courses"):
            recommended = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("learning path"):
            path = line.split(":", 1)[-1].strip()

    award_xp(session["user_id"], 20, "Skill Analysis Run")

    return jsonify({
        "fallback": False,
        "missing_skills": missing,
        "recommended_courses": recommended,
        "learning_path": path,
    })


# ---------------------------------------------------------------------------
# AI Mentor with Rich Multi-Language Knowledge Engine
# ---------------------------------------------------------------------------
PROGRAMMING_KNOWLEDGE_BASE = {
    # PYTHON
    "decorators": (
        "In Python, a **decorator** is a callable that takes a function as input and returns a modified function without altering the original code. "
        "They use the `@decorator_name` syntax.\n\n"
        "```python\n"
        "def timer(func):\n"
        "    def wrapper(*args, **kwargs):\n"
        "        print('Executing function...')\n"
        "        return func(*args, **kwargs)\n"
        "    return wrapper\n\n"
        "@timer\n"
        "def greet(name):\n"
        "    print(f'Hello {name}!')\n"
        "```\n"
        "**Best use cases**: Logging, authentication checks, caching (`lru_cache`), and rate limiting."
    ),
    "generators": (
        "A **generator** in Python produces a sequence of values on-the-fly using `yield` instead of `return`, providing extreme memory efficiency.\n\n"
        "```python\n"
        "def count_up(n):\n"
        "    for i in range(1, n + 1):\n"
        "        yield i\n"
        "```\n"
        "Unlike lists that store everything in RAM ($O(n)$ space), generators consume $O(1)$ memory by evaluating lazily when requested via `next()`."
    ),
    "gil": (
        "The **GIL (Global Interpreter Lock)** is a mutex in CPython that allows only one native thread to execute Python bytecode at any given moment.\n\n"
        "- **CPU-bound tasks**: Use Python's `multiprocessing` module or Rust extensions to utilize multiple CPU cores in parallel.\n"
        "- **I/O-bound tasks**: Use `asyncio` or standard `threading` where threads release the GIL during network/disk wait times."
    ),
    "asyncio": (
        "`asyncio` is Python's built-in framework for writing single-threaded concurrent code using **async / await** syntax and an event loop.\n\n"
        "```python\n"
        "import asyncio\n\n"
        "async def fetch_data(api_id):\n"
        "    await asyncio.sleep(1) # Non-blocking I/O\n"
        "    return {'id': api_id, 'status': 'ok'}\n\n"
        "async def main():\n"
        "    results = await asyncio.gather(fetch_data(1), fetch_data(2))\n"
        "    print(results)\n"
        "```\n"
        "It excels at handling thousands of simultaneous WebSockets or HTTP connections with low RAM overhead."
    ),

    # JAVASCRIPT & TYPESCRIPT
    "event loop": (
        "The **JavaScript Event Loop** coordinates execution between the Call Stack, Web APIs, Microtask Queue (`Promise`, `queueMicrotask`), and Macrotask Queue (`setTimeout`, `setInterval`).\n\n"
        "1. **Call Stack**: Executes synchronous code line-by-line.\n"
        "2. **Microtasks**: Run immediately after current synchronous code finishes, before rendering.\n"
        "3. **Macrotasks**: Executed one-by-one in subsequent event loop ticks."
    ),
    "closures": (
        "A **closure** in JavaScript is the combination of a function bundled together with references to its surrounding lexical environment.\n\n"
        "```javascript\n"
        "function createCounter() {\n"
        "    let count = 0; // Private state\n"
        "    return () => ++count;\n"
        "}\n"
        "const counter = createCounter();\n"
        "console.log(counter()); // 1\n"
        "console.log(counter()); // 2\n"
        "```\n"
        "Closures allow functions to retain access to variables in their parent scope even after the parent function has executed."
    ),
    "typescript generics": (
        "**Generics** in TypeScript allow you to write reusable, type-safe functions and data structures without locking into specific concrete types.\n\n"
        "```typescript\n"
        "function identity<T>(arg: T): T {\n"
        "    return arg;\n"
        "}\n"
        "const num = identity<number>(42);\n"
        "const str = identity<string>('SkillSphere');\n"
        "```\n"
        "Combine them with `Partial<T>`, `Pick<T, K>`, and `Record<K, V>` to create resilient, self-documenting codebases."
    ),

    # SQL & DATABASES
    "indexing": (
        "A **database index** (typically a B-Tree) speeds up data retrieval operations on a database table at the cost of additional storage and slower writes (`INSERT`/`UPDATE`).\n\n"
        "- **Clustered Index**: Determines the physical order of data rows on disk (usually Primary Key).\n"
        "- **Non-Clustered Index**: A separate structure storing pointers to the actual data rows.\n\n"
        "**Pro Tip**: Index columns used frequently in `WHERE`, `JOIN`, and `ORDER BY` clauses, but avoid over-indexing small or write-heavy tables."
    ),
    "window functions": (
        "**SQL Window Functions** perform calculations across a set of table rows related to the current row without collapsing them into a single summary row like `GROUP BY`.\n\n"
        "```sql\n"
        "SELECT \n"
        "    employee_id, department, salary,\n"
        "    RANK() OVER (PARTITION BY department ORDER BY salary DESC) as dept_rank,\n"
        "    AVG(salary) OVER (PARTITION BY department) as dept_avg_salary\n"
        "FROM employees;\n"
        "```\n"
        "Common window functions: `ROW_NUMBER()`, `RANK()`, `DENSE_RANK()`, `LEAD()`, `LAG()`."
    ),
    "acid": (
        "**ACID** represents the four key properties that guarantee reliable database transactions:\n\n"
        "1. **Atomicity**: All operations in a transaction succeed, or the entire transaction is rolled back.\n"
        "2. **Consistency**: Transactions transition the database from one valid state to another, enforcing constraints.\n"
        "3. **Isolation**: Concurrent transactions execute independently without interfering with each other.\n"
        "4. **Durability**: Once committed, changes survive system failures and power losses."
    ),

    # JAVA & C++
    "polymorphism": (
        "**Polymorphism** allows objects of different classes to be treated as objects of a common superclass while executing method behavior specific to their actual type.\n\n"
        "- **Compile-time (Static)**: Method Overloading.\n"
        "- **Runtime (Dynamic)**: Method Overriding using virtual functions in C++ or standard overridden methods in Java."
    ),
    "memory management": (
        "In C++, memory is allocated on either the **Stack** (automatic lifetime, fast, limited size) or the **Heap** (`new`/`malloc`, manually managed).\n\n"
        "**Modern Best Practice**: Always prefer **Smart Pointers** (`std::unique_ptr`, `std::shared_ptr`) to implement RAII (Resource Acquisition Is Initialization) and prevent memory leaks without manual `delete` calls."
    ),

    # GO & RUST
    "rust ownership": (
        "Rust enforces memory safety at compile time through its **Ownership and Borrowing** model without needing a Garbage Collector:\n\n"
        "1. Each value in Rust has an owner variable.\n"
        "2. There can only be one owner at a time.\n"
        "3. When the owner goes out of scope, the memory is dropped automatically.\n"
        "4. **Borrowing**: You can have any number of immutable references (`&T`) OR exactly one mutable reference (`&mut T`) at any given time, preventing data races."
    ),
    "goroutines": (
        "In Go, a **goroutine** is a lightweight thread of execution managed by the Go runtime scheduler rather than the OS kernel. It starts with only ~2KB of stack space.\n\n"
        "```go\n"
        "go doWork()\n"
        "```\n"
        "Goroutines communicate and synchronize safely using typed **Channels** (`ch <- value` and `value := <-ch`) following the philosophy: *'Do not communicate by sharing memory; instead, share memory by communicating.'*"
    )
}


@app.route("/mentor")
@login_required
def mentor():
    return render_template("mentor.html", gemini_configured=bool(gemini_model))


@app.route("/mentor/ask", methods=["POST"])
@login_required
def mentor_ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"reply": "Please enter a coding or technical question."})

    # First check if live Gemini is configured
    if gemini_model:
        prompt = f"""You are a helpful, clear, and encouraging senior software engineer and AI learning mentor on SkillSphere AI.
Answer the student's question accurately with clear explanation and a clean code example where appropriate.

Student question: {question}
"""
        reply = ask_gemini(prompt)
        if reply:
            award_xp(session["user_id"], 15, "AI Mentor Question")
            return jsonify({"reply": reply})

    # Comprehensive smart local knowledge base matching
    q_lower = question.lower()
    matched_reply = None
    for keyword, explanation in PROGRAMMING_KNOWLEDGE_BASE.items():
        if keyword in q_lower:
            matched_reply = explanation
            break

    if not matched_reply:
        if "python" in q_lower:
            matched_reply = (
                "Python is an intuitive, high-level language with dynamic typing and automatic memory management. "
                "Core areas to master: Data Structures (lists, dicts, sets), Object-Oriented Programming (dunder methods), "
                "Generators/Iterators, Decorators, and Async/Await for concurrent I/O."
            )
        elif "javascript" in q_lower or "js" in q_lower:
            matched_reply = (
                "JavaScript is the asynchronous, event-driven language of the modern web. "
                "Key concepts to master: The Event Loop, Promises & async/await, Lexical Closures, ES6 Modules, "
                "and Frameworks like React / Vue."
            )
        elif "sql" in q_lower or "database" in q_lower:
            matched_reply = (
                "In SQL and Relational Databases, focus on mastering ACID transactions, B-Tree Indexing strategies, "
                "multi-table JOIN optimizations, Subqueries vs CTEs, and Window Functions (`ROW_NUMBER`, `RANK`)."
            )
        elif "java" in q_lower or "c++" in q_lower:
            matched_reply = (
                "For Java & C++, master strong Object-Oriented Architecture (SOLID principles), Design Patterns (Factory, Singleton, Observer), "
                "Memory Management (Heap vs Stack, Garbage Collection in Java, RAII & Smart Pointers in C++)."
            )
        else:
            matched_reply = (
                f"Great question regarding **'{question}'**! "
                "When tackling this concept, start by breaking it down into its core primitives, test with small hands-on code experiments in our AI Code Studio, "
                "and review the corresponding lessons in the Courses tab."
            )

    award_xp(session["user_id"], 15, "AI Mentor Question")
    return jsonify({"reply": matched_reply, "fallback": True})


# ---------------------------------------------------------------------------
# AI Code Studio & Smart Reviewer
# ---------------------------------------------------------------------------
CHALLENGE_LIBRARY = {
    "twosum": {
        "title": "Two Sum (Hash Map)",
        "difficulty": "Easy",
        "language": "python",
        "description": "Given an array of integers `nums` and an integer `target`, return indices of the two numbers that add up to `target` in $O(n)$ time.",
        "starter_code": """def two_sum(nums, target):
    # Dict to map value -> index
    seen = {}
    for i, n in enumerate(nums):
        diff = target - n
        if diff in seen:
            return [seen[diff], i]
        seen[n] = i
    return []

# Test execution
nums = [2, 7, 11, 15]
target = 9
print("Target 9 Result:", two_sum(nums, target))
"""
    },
    "valid_parentheses": {
        "title": "Valid Parentheses (Stack)",
        "difficulty": "Easy",
        "language": "python",
        "description": "Given a string `s` containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.",
        "starter_code": """def is_valid(s: str) -> bool:
    stack = []
    mapping = {")": "(", "}": "{", "]": "["}
    for char in s:
        if char in mapping:
            top = stack.pop() if stack else '#'
            if mapping[char] != top:
                return False
        else:
            stack.append(char)
    return not stack

print("Is '()[]{}' valid?", is_valid("()[]{}"))
print("Is '(]' valid?", is_valid("(]"))
"""
    },
    "lru_cache": {
        "title": "LRU Cache Implementation",
        "difficulty": "Medium",
        "language": "python",
        "description": "Design a data structure that follows the constraints of a Least Recently Used (LRU) cache with $O(1)$ get and put operations.",
        "starter_code": """class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {} # In Python 3.7+, dict preserves insertion order

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        val = self.cache.pop(key)
        self.cache[key] = val
        return val

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.pop(key)
        elif len(self.cache) >= self.capacity:
            # Pop oldest item
            oldest_key = next(iter(self.cache))
            self.cache.pop(oldest_key)
        self.cache[key] = value

lru = LRUCache(2)
lru.put(1, 100)
lru.put(2, 200)
print("Get 1:", lru.get(1))
lru.put(3, 300) # Evicts key 2
print("Get 2 (should be -1):", lru.get(2))
"""
    },
    "sql_window": {
        "title": "SQL Leaderboard Window Ranking",
        "difficulty": "Medium",
        "language": "sql",
        "description": "Calculate dynamic rankings and cumulative completion metrics across learners using SQL Window Functions.",
        "starter_code": """-- Rank active learners by completed courses using DENSE_RANK
SELECT 
    u.id,
    u.name,
    COUNT(e.id) AS completed_courses,
    DENSE_RANK() OVER (ORDER BY COUNT(e.id) DESC) as platform_rank,
    AVG(COUNT(e.id)) OVER () as avg_courses_completed
FROM users u
LEFT JOIN enrollments e ON u.id = e.user_id AND e.progress = 100
GROUP BY u.id, u.name;
"""
    },
    "debounce_js": {
        "title": "Debounce Function Implementation",
        "difficulty": "Medium",
        "language": "javascript",
        "description": "Create a debounce wrapper function in JavaScript to optimize high-frequency events like search input keystrokes.",
        "starter_code": """function debounce(func, delayMs) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delayMs);
    };
}

const onSearch = debounce((query) => {
    console.log("Searching API for:", query);
}, 300);

onSearch("Py");
onSearch("Python");
onSearch("Python Decorators");
"""
    }
}


@app.route("/code-studio")
@login_required
def code_studio():
    recent_reviews = run_query(
        "SELECT * FROM code_reviews WHERE user_id = %s ORDER BY created_at DESC LIMIT 5",
        (session["user_id"],), fetch=True
    ) or []
    return render_template("code_studio.html", challenges=CHALLENGE_LIBRARY, recent_reviews=recent_reviews)


@app.route("/code-studio/review", methods=["POST"])
@login_required
def code_studio_review():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    language = data.get("language", "python").strip()

    if not code:
        return jsonify({"error": "No code provided for review."}), 400

    prompt = f"""You are an expert software engineer and AI code reviewer.
Analyze this {language} code snippet:

```{language}
{code}
```

Provide structured analysis in JSON format with these exact keys:
{{
  "quality_score": <integer from 1 to 100>,
  "time_complexity": "<e.g. O(n) or O(1)>",
  "space_complexity": "<e.g. O(1) or O(n)>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "issues_or_smells": ["<issue 1>", "<issue 2>"],
  "refactored_code": "<clean refactored version of the code>",
  "overall_verdict": "<short 1-2 sentence encouraging summary>"
}}
Output ONLY valid JSON.
"""

    reply = ask_gemini(prompt)
    review_data = None
    if reply:
        try:
            clean_json = reply.strip()
            if clean_json.startswith("```json"): clean_json = clean_json[7:]
            if clean_json.startswith("```"): clean_json = clean_json[3:]
            if clean_json.endswith("```"): clean_json = clean_json[:-3]
            review_data = json.loads(clean_json.strip())
        except Exception:
            pass

    if not review_data:
        has_docstring = '"""' in code or "'''" in code
        has_loops = "for " in code or "while " in code
        score = 85 if has_docstring else 78
        if "seen" in code or "dict" in code or "stack" in code: score += 10
        
        review_data = {
            "quality_score": min(98, max(70, score)),
            "time_complexity": "O(n)" if has_loops else "O(1)",
            "space_complexity": "O(n)" if ("seen" in code or "cache" in code or "stack" in code) else "O(1)",
            "strengths": [
                f"Clean and idiomatic {language.capitalize()} implementation",
                "Efficient space-time trade-off with clear data structure selection"
            ],
            "issues_or_smells": [
                "Consider adding explicit boundary and empty-input validation checks",
                "Ensure type annotations and docstrings comply with standard styling conventions"
            ],
            "refactored_code": f"# Refactored & Production-Ready {language.capitalize()} Solution\n" + code,
            "overall_verdict": "Great work! The core logic is sound and runs with optimal algorithmic complexity."
        }

    run_query(
        "INSERT INTO code_reviews (user_id, language, code_snippet, ai_review) VALUES (%s, %s, %s, %s)",
        (session["user_id"], language, code[:500], json.dumps(review_data)),
        commit=True
    )
    award_xp(session["user_id"], 35, "Code Reviewed", "Code Samurai")

    return jsonify({"success": True, "review": review_data})


# ---------------------------------------------------------------------------
# AI Technical Mock Interview Simulator
# ---------------------------------------------------------------------------
MOCK_ROLE_CATALOG = {
    "python": {
        "title": "Python Backend Engineer",
        "junior": "Explain the difference between mutable (lists, dicts) and immutable (tuples, strings) types in Python. How does passing them into functions behave?",
        "mid": "How does Python handle memory management with reference counting vs cyclic garbage collection? How would you profile memory bottlenecks in FastAPI or Django?",
        "senior": "Architect a distributed task processing pipeline in Python handling 100k jobs/sec. How would you handle idempotency, dead-letter queues, and worker backpressure with Celery/Redis/Kafka?"
    },
    "data_science": {
        "title": "Data Scientist & ML Engineer",
        "junior": "What is the difference between Supervised and Unsupervised Learning? Give two real-world algorithmic examples of each.",
        "mid": "Explain the Bias-Variance tradeoff. What concrete techniques do you use to detect and mitigate overfitting in Gradient Boosted Decision Trees (XGBoost/LightGBM)?",
        "senior": "Design an end-to-end real-time vector search & RAG pipeline for 10 million enterprise documents. How do you manage embedding drift, hybrid sparse/dense retrieval, and latency SLAs?"
    },
    "fullstack": {
        "title": "Full-Stack Web Engineer",
        "junior": "Explain the CSS Box Model and the difference between synchronous vs asynchronous code execution in JavaScript.",
        "mid": "How do you manage race conditions in asynchronous frontend state updates and ensure database ACID consistency under heavy concurrent writes?",
        "senior": "Design a real-time collaborative document editing system (like Google Docs). How do you handle conflict resolution (OT vs CRDT), WebSocket connection scaling, and offline syncing?"
    },
    "cloud": {
        "title": "Cloud DevOps & SRE",
        "junior": "What is the difference between a Virtual Machine and a Docker Container? Explain how container layers work.",
        "mid": "Describe your strategy for zero-downtime deployments in Kubernetes. How do readiness probes, rolling updates, and canary traffic shaping cooperate?",
        "senior": "Design a multi-region, active-active cloud disaster recovery architecture with RPO < 1 min and RTO < 5 min. How do you handle database cross-region replication and DNS failover?"
    }
}


@app.route("/interview")
@login_required
def interview():
    history = run_query(
        "SELECT * FROM mock_interviews WHERE user_id = %s ORDER BY created_at DESC LIMIT 6",
        (session["user_id"],), fetch=True
    ) or []
    return render_template("interview.html", roles=MOCK_ROLE_CATALOG, history=history)


@app.route("/interview/generate", methods=["POST"])
@login_required
def interview_generate():
    data = request.get_json(silent=True) or {}
    role_key = data.get("role", "python")
    difficulty = data.get("difficulty", "mid").lower()

    catalog_entry = MOCK_ROLE_CATALOG.get(role_key, MOCK_ROLE_CATALOG["python"])
    role_name = catalog_entry["title"]

    prompt = f"""You are a senior tech lead conducting a technical interview for a {difficulty.upper()} level {role_name}.
Generate ONE challenging, practical interview question. Return ONLY the question text without labels."""

    question = ask_gemini(prompt)
    if not question:
        question = catalog_entry.get(difficulty, catalog_entry["mid"])

    return jsonify({"role": role_name, "difficulty": difficulty.capitalize(), "question": question.strip()})


@app.route("/interview/evaluate", methods=["POST"])
@login_required
def interview_evaluate():
    data = request.get_json(silent=True) or {}
    role = data.get("role", "Software Engineer")
    question = data.get("question", "")
    answer = data.get("answer", "").strip()

    if not answer:
        return jsonify({"error": "Please provide your answer before submitting."}), 400

    prompt = f"""You are an expert interviewer evaluating a candidate for {role}.
Question: {question}
Candidate Answer: {answer}

Evaluate this answer and return ONLY valid JSON:
{{
  "score": <integer from 1 to 100>,
  "strengths": "<2-3 sentence summary of good points>",
  "improvements": "<2-3 key points candidate missed or could improve>",
  "ideal_answer": "<concise, perfect model answer for this question>"
}}
"""

    reply = ask_gemini(prompt)
    eval_data = None
    if reply:
        try:
            clean_json = reply.strip()
            if clean_json.startswith("```json"): clean_json = clean_json[7:]
            if clean_json.startswith("```"): clean_json = clean_json[3:]
            if clean_json.endswith("```"): clean_json = clean_json[:-3]
            eval_data = json.loads(clean_json.strip())
        except Exception:
            pass

    if not eval_data:
        word_count = len(answer.split())
        score = min(94, max(55, 65 + word_count // 3))
        eval_data = {
            "score": score,
            "strengths": "Demonstrates clear conceptual foundation, sound logic, and relevant technical terminology.",
            "improvements": "Consider elaborating on edge cases, operational trade-offs, and scalability bottlenecks.",
            "ideal_answer": f"A comprehensive model response to this question articulates the underlying mechanism clearly, highlights trade-offs, and references production engineering best practices."
        }

    run_query(
        """INSERT INTO mock_interviews 
           (user_id, role, question, answer, score, feedback, strengths, improvements, ideal_answer) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (session["user_id"], role, question, answer, eval_data["score"],
         f"Scored {eval_data['score']}/100", eval_data["strengths"],
         eval_data["improvements"], eval_data["ideal_answer"]),
        commit=True
    )
    award_xp(session["user_id"], 75, "Mock Interview Completed", "Interview Ace")

    return jsonify({"success": True, "evaluation": eval_data})


# ---------------------------------------------------------------------------
# Career Roadmap & Project Studio
# ---------------------------------------------------------------------------
DEFAULT_ROADMAP_MILESTONES = [
    {
        "id": 1,
        "step": 1,
        "title": "Programming & Core Foundations",
        "duration": "2 Weeks",
        "skills": ["Python / JavaScript", "Control Flow", "Object-Oriented Design", "Git Version Control"],
        "project": "Build an Automated Data Parser & Interactive CLI Tool",
        "completed": True
    },
    {
        "id": 2,
        "step": 2,
        "title": "Databases & Backend Systems",
        "duration": "3 Weeks",
        "skills": ["Relational SQL", "Query Optimization", "RESTful APIs", "Flask / FastAPI"],
        "project": "Design a Scalable Multi-Tenant REST API with SQLite/Postgres",
        "completed": True
    },
    {
        "id": 3,
        "step": 3,
        "title": "Machine Learning & AI Integration",
        "duration": "4 Weeks",
        "skills": ["Supervised ML", "LLM APIs & Prompt Engineering", "Vector Embeddings", "RAG Pipelines"],
        "project": "Build an AI-Powered Document Assistant with Retrieval Augmented Generation",
        "completed": False
    },
    {
        "id": 4,
        "step": 4,
        "title": "Cloud Architecture & DevOps CI/CD",
        "duration": "3 Weeks",
        "skills": ["Docker Containerization", "Cloud Deployment", "CI/CD Workflows", "Security & Monitoring"],
        "project": "Deploy Full-Stack Containerized App with Automated CI/CD Pipelines",
        "completed": False
    },
    {
        "id": 5,
        "step": 5,
        "title": "Production Capstone & Interview Readiness",
        "duration": "2 Weeks",
        "skills": ["System Design", "Microservices Architecture", "Performance Benchmarking"],
        "project": "Enterprise-Grade Skill Development Platform Capstone",
        "completed": False
    }
]


@app.route("/roadmap")
@login_required
def roadmap():
    user_id = session["user_id"]
    rm = run_query("SELECT * FROM roadmaps WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,), fetchone=True)
    
    if rm:
        try:
            milestones = json.loads(rm["milestones_json"])
            target_role = rm["target_role"]
        except Exception:
            milestones = DEFAULT_ROADMAP_MILESTONES
            target_role = "Full-Stack AI & Cloud Engineer"
    else:
        milestones = DEFAULT_ROADMAP_MILESTONES
        target_role = "Full-Stack AI & Cloud Engineer"

    completed_count = sum(1 for m in milestones if m.get("completed"))
    percent = round((completed_count / len(milestones)) * 100) if milestones else 0

    return render_template("roadmap.html", target_role=target_role, milestones=milestones, completion_percent=percent)


@app.route("/roadmap/generate", methods=["POST"])
@login_required
def roadmap_generate():
    data = request.get_json(silent=True) or {}
    target_role = data.get("target_role", "").strip() or "AI Solutions Architect"
    timeframe = data.get("timeframe", "60 Days").strip()

    prompt = f"""Generate a structured, progressive 5-milestone learning roadmap for someone aiming to become a '{target_role}' in {timeframe}.
Return ONLY valid JSON array with 5 items:
[
  {{
    "id": 1,
    "step": 1,
    "title": "<Milestone Title>",
    "duration": "<e.g. 2 Weeks>",
    "skills": ["<skill1>", "<skill2>", "<skill3>"],
    "project": "<Realistic portfolio project to build>",
    "completed": false
  }}
]
"""
    reply = ask_gemini(prompt)
    milestones = None
    if reply:
        try:
            clean_json = reply.strip()
            if clean_json.startswith("```json"): clean_json = clean_json[7:]
            if clean_json.startswith("```"): clean_json = clean_json[3:]
            if clean_json.endswith("```"): clean_json = clean_json[:-3]
            milestones = json.loads(clean_json.strip())
        except Exception:
            pass

    if not milestones:
        milestones = [
            {"id": 1, "step": 1, "title": f"{target_role} Core Foundations", "duration": "2 Weeks", "skills": ["Core Languages", "Data Modeling", "Git"], "project": "Foundational Architecture CLI", "completed": True},
            {"id": 2, "step": 2, "title": "Frameworks & Backend Pipelines", "duration": "3 Weeks", "skills": ["APIs", "Database Indexing", "Async Processing"], "project": "High-Throughput Ingestion Service", "completed": False},
            {"id": 3, "step": 3, "title": "AI & Advanced Specialization", "duration": "3 Weeks", "skills": ["LLMs", "Vector Search", "Evaluation Metrics"], "project": "Intelligent Agent Workflow", "completed": False},
            {"id": 4, "step": 4, "title": "Cloud Scale & Reliability", "duration": "2 Weeks", "skills": ["Kubernetes", "Observability", "Security"], "project": "Production Multi-Cloud Cluster", "completed": False},
            {"id": 5, "step": 5, "title": "Capstone & Technical Mastery", "duration": "2 Weeks", "skills": ["System Design", "Enterprise Scalability"], "project": f"Production-Grade {target_role} Showcase", "completed": False},
        ]

    run_query(
        "INSERT INTO roadmaps (user_id, target_role, milestones_json) VALUES (%s, %s, %s)",
        (session["user_id"], target_role, json.dumps(milestones)),
        commit=True
    )
    award_xp(session["user_id"], 40, "Roadmap Created", "Pathfinder")

    return jsonify({"success": True, "milestones": milestones})


@app.route("/roadmap/toggle", methods=["POST"])
@login_required
def roadmap_toggle():
    data = request.get_json(silent=True) or {}
    milestone_id = data.get("milestone_id")
    user_id = session["user_id"]

    rm = run_query("SELECT * FROM roadmaps WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,), fetchone=True)
    if not rm:
        milestones = DEFAULT_ROADMAP_MILESTONES
        for m in milestones:
            if m["id"] == milestone_id:
                m["completed"] = not m.get("completed", False)
        run_query(
            "INSERT INTO roadmaps (user_id, target_role, milestones_json) VALUES (%s, %s, %s)",
            (user_id, "Full-Stack AI & Cloud Engineer", json.dumps(milestones)),
            commit=True
        )
    else:
        milestones = json.loads(rm["milestones_json"])
        for m in milestones:
            if m["id"] == milestone_id:
                m["completed"] = not m.get("completed", False)
        run_query(
            "UPDATE roadmaps SET milestones_json = %s WHERE id = %s",
            (json.dumps(milestones), rm["id"]),
            commit=True
        )

    award_xp(user_id, 25, "Milestone Progress")
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Leaderboard, Badges & XP System
# ---------------------------------------------------------------------------
BADGE_DEFINITIONS = [
    {"name": "Welcome Explorer", "icon": "bi-compass-fill", "desc": "Joined SkillSphere AI platform", "color": "text-primary"},
    {"name": "Python Pioneer", "icon": "bi-code-slash", "desc": "Mastered core Python workflows", "color": "text-info"},
    {"name": "Quiz Whiz", "icon": "bi-patch-check-fill", "desc": "Scored 100% on technical assessment", "color": "text-success"},
    {"name": "Code Samurai", "icon": "bi-cpu-fill", "desc": "Completed AI Code Studio reviews", "color": "text-warning"},
    {"name": "Interview Ace", "icon": "bi-mic-fill", "desc": "Completed technical mock interviews", "color": "text-danger"},
    {"name": "Pathfinder", "icon": "bi-map-fill", "desc": "Generated custom career roadmap", "color": "text-secondary"},
    {"name": "Certified Specialist", "icon": "bi-award-fill", "desc": "Earned official course certificate", "color": "text-warning"},
    {"name": "Grandmaster", "icon": "bi-trophy-fill", "desc": "Surpassed 1,200 XP points", "color": "text-warning"},
]


@app.route("/leaderboard")
@login_required
def leaderboard():
    users_gamification = run_query(
        """SELECT u.id, u.name, u.role, g.xp, g.streak, g.level, g.badges
           FROM users u
           LEFT JOIN user_gamification g ON u.id = g.user_id
           ORDER BY COALESCE(g.xp, 0) DESC""",
        fetch=True
    ) or []

    for u in users_gamification:
        u["xp"] = u.get("xp") or 0
        u["streak"] = u.get("streak") or 1
        u["level"] = u.get("level") or 1
        try:
            u["badges_list"] = json.loads(u["badges"]) if u.get("badges") else ["Welcome Explorer"]
        except Exception:
            u["badges_list"] = ["Welcome Explorer"]

    return render_template(
        "leaderboard.html",
        leaderboard=users_gamification,
        all_badges=BADGE_DEFINITIONS
    )


# ---------------------------------------------------------------------------
# Knowledge Hub
# ---------------------------------------------------------------------------
@app.route("/hub", methods=["GET", "POST"])
@login_required
def hub():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if title and content:
            run_query(
                "INSERT INTO discussions (user_id, title, content) VALUES (%s, %s, %s)",
                (session["user_id"], title, content), commit=True,
            )
            award_xp(session["user_id"], 25, "Discussion Posted", "Community Contributor")
            flash("Discussion topic posted successfully! (+25 XP)", "success")
        else:
            flash("Title and content are required.", "danger")
        return redirect(url_for("hub"))

    discussions = run_query(
        """SELECT d.*, u.name AS author, u.role AS author_role FROM discussions d
           JOIN users u ON d.user_id = u.id
           ORDER BY d.created_at DESC""",
        fetch=True,
    ) or []
    return render_template("hub.html", discussions=discussions)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
@app.route("/profile")
@login_required
def profile():
    user = run_query("SELECT * FROM users WHERE id = %s", (session["user_id"],), fetchone=True)

    skills_data = run_query(
        "SELECT name, score FROM skills WHERE user_id = %s", (session["user_id"],), fetch=True
    ) or []
    avg_score = round(sum(s["score"] for s in skills_data) / len(skills_data)) if skills_data else 0

    completed = run_query(
        "SELECT COUNT(*) AS c FROM enrollments WHERE user_id = %s AND progress = 100",
        (session["user_id"],), fetchone=True,
    ) or {"c": 0}

    certificates = run_query(
        """SELECT cert.certificate_id, cert.date, c.title AS course_title
           FROM certificates cert JOIN courses c ON cert.course_id = c.id
           WHERE cert.user_id = %s ORDER BY cert.date DESC""",
        (session["user_id"],), fetch=True,
    ) or []

    gamification = get_gamification(session["user_id"])

    return render_template(
        "profile.html",
        user=user,
        skill_score=avg_score,
        completed_courses=completed.get("c", 0),
        certificates=certificates,
        gamification=gamification,
    )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    flash("The requested page was not found.", "warning")
    return redirect(url_for("dashboard") if "user_id" in session else url_for("index"))


@app.errorhandler(500)
def server_error(e):
    flash("Something went wrong on our end. Please try again.", "danger")
    return redirect(url_for("dashboard") if "user_id" in session else url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
