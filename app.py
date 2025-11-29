from flask import (
    Flask, render_template, request, redirect, session, flash,
    url_for, jsonify, send_from_directory
)
from flask_mysql_connector import MySQL
from flask_bcrypt import Bcrypt
import re
import os
from werkzeug.utils import secure_filename
import json
import uuid
import datetime

# ----------------- App setup -----------------
app = Flask(__name__)

app.secret_key = '9f8b2c6a3d8e47f98a9e1a7c4b8d3f1e'

# MySQL config (adjust for your environment)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password'
app.config['MYSQL_DATABASE'] = 'plant_disease_db'

mysql = MySQL(app)
bcrypt = Bcrypt(app)

# ----------------- Model import -----------------
try:
    from models import main as plant_model
    print("models.main imported OK")
except Exception as e:
    plant_model = None
    print("models.main import failed:", e)

# ----------------- File / upload helpers -----------------
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ----------------- History (JSON) helpers -----------------
HISTORY_PATH = os.path.join(os.path.dirname(__file__), 'predictions_history.json')


def _read_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _write_history(records):
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def save_prediction_to_history(username, image_relpath, result_dict, lang='en'):
    """
    Save a prediction record and return its id.
    result_dict should include keys: label, confidence, advice, health_status
    lang is the selected language code ('en','hi','mr') to store with the record.
    """
    records = _read_history()
    rid = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    rec = {
        "id": rid,
        "username": username,
        "timestamp": now,
        "image": image_relpath,   # 'uploads/<filename>'
        "label": result_dict.get("label"),
        "confidence": result_dict.get("confidence"),
        "advice": result_dict.get("advice"),
        "health_status": result_dict.get("health_status"),
        "feedback": None,
        "lang": lang
    }
    records.insert(0, rec)  # newest first
    _write_history(records)
    return rid


# ----------------- Routes -----------------
@app.route('/')
def home():
    return redirect(url_for('login'))


# -------- Authentication (register/login/logout) --------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Invalid email address!', 'danger')
            return redirect(url_for('register'))

        if not re.match(r'^[A-Za-z0-9]+$', username):
            flash('Username must contain only characters and numbers!', 'danger')
            return redirect(url_for('register'))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()

        if account:
            flash('Email already exists! Please log in.', 'warning')
        else:
            cursor.execute(
                'INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)',
                (username, email, hashed_pw, 'user')
            )
            mysql.connection.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()

        if account and bcrypt.check_password_hash(account['password'], password):
            session['loggedin'] = True
            session['username'] = account['username']
            session['role'] = account['role']
            # Preserve any previously selected language in session if exists (no change here)
            if account['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid email or password!', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


# -------- Language setter route --------
@app.route('/set_language/<lang>')
def set_language(lang):
    """
    Set user's preferred language in session.
    Accepts only 'en', 'hi', 'mr' (case-insensitive).

    - If called via AJAX (navbar buttons), return JSON.
    - If normal link, do the old redirect behaviour.
    """
    lang = (lang or 'en').lower()
    if lang not in ('en', 'hi', 'mr'):
        lang = 'en'
    session['lang'] = lang

    # NEW: if this is an AJAX / JSON request from JS, return JSON instead of redirect
    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )
    if wants_json:
        return jsonify({"ok": True, "lang": lang})

    # Old logic kept for normal navigation
    ref = request.headers.get('Referer')
    if ref:
        return redirect(ref)
    return redirect(url_for('user_dashboard'))


# -------- Dashboards --------
@app.route('/user_dashboard')
def user_dashboard():
    if 'loggedin' in session and session.get('role') == 'user':
        username = session['username']
        records = _read_history()
        user_records = [r for r in records if r.get('username') == username]
        recent = user_records[:5]
        lang = session.get('lang', 'en')
        return render_template('user_dashboard.html', username=username, history=recent, lang=lang)
    flash('Please log in as user', 'danger')
    return redirect(url_for('login'))


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'loggedin' in session and session.get('role') == 'admin':
        username = session['username']

        # ---- NEW: admin features (only data fetch, no change to user logic) ----
        # 1) Manage users: get list of all users
        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute('SELECT id, username, email, role FROM users ORDER BY id ASC')
        users = cursor.fetchall()

        # 2) View feedback: read from predictions_history.json where feedback is present
        records = _read_history()
        feedback_records = []
        for r in records:
            fb = r.get('feedback')
            if fb:
                feedback_records.append({
                    "id": r.get("id"),
                    "username": r.get("username"),
                    "label": r.get("label"),
                    "timestamp": r.get("timestamp"),
                    "feedback_user": fb.get("user"),
                    "feedback_text": fb.get("text"),
                    "feedback_time": fb.get("time")
                })

        # show most recent first
        feedback_records = sorted(
            feedback_records,
            key=lambda x: x.get("feedback_time") or "",
            reverse=True
        )

        return render_template(
            'admin_dashboard.html',
            username=username,
            users=users,
            feedback_records=feedback_records
        )

    flash('Please log in as admin', 'danger')
    return redirect(url_for('login'))


@app.route('/admin/users')
def admin_users():
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute('SELECT id, username, email, role FROM users ORDER BY id ASC')
    users = cursor.fetchall()

    return render_template('admin_users.html', users=users)


@app.route('/admin/feedback')
def admin_feedback():
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))

    records = _read_history()
    feedback_records = []

    for r in records:
        fb = r.get("feedback")
        if fb:
            feedback_records.append({
                "id": r.get("id"),
                "username": r.get("username"),
                "label": r.get("label"),
                "timestamp": r.get("timestamp"),
                "feedback_user": fb.get("user"),
                "feedback_text": fb.get("text"),
                "feedback_time": fb.get("time")
            })

    feedback_records = sorted(
        feedback_records,
        key=lambda x: x.get("feedback_time") or "",
        reverse=True
    )

    return render_template('admin_feedback.html', feedback_records=feedback_records)


# -------- Serve uploaded images --------
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    uploads_dir = os.path.join(os.path.dirname(__file__), 'models', 'uploads')
    return send_from_directory(uploads_dir, filename)


# -------- Prediction upload endpoint (POST) --------
@app.route('/predict_file', methods=['POST'])
def predict_file():
    if 'loggedin' not in session:
        flash('Please log in to upload', 'danger')
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('No file provided', 'danger')
        return redirect(url_for('user_dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('user_dashboard'))

    if not allowed_file(file.filename):
        flash('Invalid file type', 'danger')
        return redirect(url_for('user_dashboard'))

    filename = secure_filename(file.filename)
    upload_dir = os.path.join(os.path.dirname(__file__), 'models', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    name_root, ext = os.path.splitext(filename)
    unique_name = f"{name_root}_{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, unique_name)
    file.save(file_path)

    if plant_model is None:
        flash('Model not available on server', 'danger')
        return redirect(url_for('user_dashboard'))

    try:
        # model returns dict with keys label, confidence, advice, health_status
        result = plant_model.predict_image(file_path)
    except Exception as e:
        flash('Prediction failed: ' + str(e), 'danger')
        return redirect(url_for('user_dashboard'))

    username = session.get('username', 'anonymous')
    image_relpath = f"uploads/{unique_name}"
    lang = session.get('lang', 'en')
    rid = save_prediction_to_history(username, image_relpath, result, lang=lang)

    return redirect(url_for('prediction_result', record_id=rid))


# -------- Prediction result page --------
@app.route('/prediction_result/<record_id>')
def prediction_result(record_id):
    if 'loggedin' not in session:
        flash('Please log in to view results', 'danger')
        return redirect(url_for('login'))
    records = _read_history()
    rec = next((r for r in records if r['id'] == record_id), None)
    if rec is None:
        flash('Result not found', 'warning')
        return redirect(url_for('user_dashboard'))

    # Authorization: owner or admin
    if rec['username'] != session.get('username') and session.get('role') != 'admin':
        flash('You are not authorized to view this result', 'danger')
        return redirect(url_for('user_dashboard'))

    # choose language: prefer session, then record.lang, then default 'en'
    lang = session.get('lang', rec.get('lang', 'en') if isinstance(rec.get('lang'), str) else 'en')
    return render_template('result.html', record=rec, lang=lang)


# -------- Feedback endpoint (POST) --------
@app.route('/feedback', methods=['POST'])
def feedback():
    if 'loggedin' not in session:
        flash('Please log in to send feedback', 'danger')
        return redirect(url_for('login'))

    record_id = request.form.get('record_id')
    feedback_text = request.form.get('feedback')
    if not record_id or feedback_text is None:
        flash('Feedback missing', 'danger')
        return redirect(url_for('user_dashboard'))

    records = _read_history()
    found = False
    for r in records:
        if r['id'] == record_id:
            r['feedback'] = {
                "user": session.get('username'),
                "text": feedback_text,
                "time": datetime.datetime.utcnow().isoformat() + 'Z'
            }
            found = True
            break

    if found:
        _write_history(records)
        flash('Thank you — feedback saved.', 'success')
        return redirect(url_for('prediction_result', record_id=record_id))
    else:
        flash('Record not found', 'danger')
        return redirect(url_for('user_dashboard'))


# -------- History page (all user's uploads) --------
@app.route('/history')
def history():
    if 'loggedin' not in session:
        flash('Please log in', 'danger')
        return redirect(url_for('login'))
    username = session.get('username')
    records = _read_history()
    user_records = [r for r in records if r.get('username') == username]
    user_records_sorted = sorted(user_records, key=lambda r: r.get('timestamp', ''), reverse=True)
    lang = session.get('lang', 'en')
    return render_template('history.html', records=user_records_sorted, lang=lang)


# -------- UI translation data for user dashboard (existing logic) --------
_UI_TRANSLATIONS = {
    "en": {
        "brand": "User Dashboard — Welcome, {username}",
        "recent_uploads_title": "Recent uploads",
        "recent_uploads_desc": "Click to view all uploaded images in a gallery.",
        "view_all": "View all →",
        "quick_actions_title": "Quick actions",
        "quick_actions_desc": "Useful shortcuts for your account.",
        "history_btn": "History",
        "upload_title": "Upload leaf image",
        "upload_desc": "Choose a clear photo to get a prediction on a result page.",
        "upload_btn": "Upload & Predict",
        "image_preview": "Image preview",
        "recent_uploads_heading": "Recent uploads (latest)",
        "view_link": "View",
        "no_recent": "No recent uploads yet.",
        "logout": "Logout",
        "feedback_placeholder": "Type feedback here..."
    },
    "hi": {
        "brand": "उपयोगकर्ता डैशबोर्ड — स्वागत है, {username}",
        "recent_uploads_title": "हाल की अपलोड",
        "recent_uploads_desc": "गैलरी में सभी अपलोड की गई छवियाँ देखने के लिए क्लिक करें।",
        "view_all": "सभी देखें →",
        "quick_actions_title": "त्वरित कार्य",
        "quick_actions_desc": "आपके खाते के लिए उपयोगी शॉर्टकट।",
        "history_btn": "इतिहास",
        "upload_title": "पत्ती की छवि अपलोड करें",
        "upload_desc": "परिणाम पृष्ठ पर भविष्यवाणी प्राप्त करने के लिए स्पष्ट फ़ोटो चुनें।",
        "upload_btn": "अपलोड और भविष्यवाणी",
        "image_preview": "छवि पूर्वावलोकन",
        "recent_uploads_heading": "हाल की अपलोड (नवीनतम)",
        "view_link": "देखें",
        "no_recent": "अभी तक कोई हालिया अपलोड नहीं।",
        "logout": "लॉग आउट",
        "feedback_placeholder": "यहाँ प्रतिक्रिया लिखें..."
    },
    "mr": {
        "brand": "युजर डॅशबोर्ड — स्वागत आहे, {username}",
        "recent_uploads_title": "अलीकडील अपलोड",
        "recent_uploads_desc": "गॅलरीमध्ये सर्व अपलोड केलेल्या प्रतिमा पाहण्यासाठी क्लिक करा.",
        "view_all": "सर्व पहा →",
        "quick_actions_title": "जलद क्रिया",
        "quick_actions_desc": "तुमच्या खात्यासाठी उपयुक्त शॉर्टकट.",
        "history_btn": "इतिहास",
        "upload_title": "पानाची प्रतिमा अपलोड करा",
        "upload_desc": "परिणाम पृष्ठावर भाकीत मिळवण्यासाठी एक स्पष्ट फोटो निवडा.",
        "upload_btn": "अपलोड & भाकीत",
        "image_preview": "प्रतिमा पूर्वदर्शनी",
        "recent_uploads_heading": "अलीकडील अपलोड (नवीनतम)",
        "view_link": "पहा",
        "no_recent": "अजून कोणतीही अलीकडील अपलोड नाहीत.",
        "logout": "लॉगआऊट",
        "feedback_placeholder": "इथे अभिप्राय लिहा..."
    }
}


@app.route('/ui_translations')
def ui_translations():
    """
    Return translation map for current language.

    JS expects: { "map": { "english text": "translated text", ... } }
    """
    lang = request.args.get('lang', 'en').lower()
    if lang not in ('en', 'hi', 'mr'):
        lang = 'en'
    data = _UI_TRANSLATIONS.get(lang, _UI_TRANSLATIONS['en'])
    # IMPORTANT: wrap in {"map": ...} to match front-end code
    return jsonify({"map": data})


# -------- Support & Edit profile (existing feature) --------
SUPPORT_PHONE = "9372383929"  # customer support number


@app.route('/support')
def support():
    if 'loggedin' not in session:
        flash('Please log in', 'danger')
        return redirect(url_for('login'))
    username = session.get('username')
    return render_template('support.html', username=username, support_phone=SUPPORT_PHONE)


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'loggedin' not in session:
        flash('Please log in to edit your profile', 'danger')
        return redirect(url_for('login'))

    username = session.get('username')

    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("SELECT id, username, email FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('user_dashboard'))

    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        new_email = request.form.get('email', '').strip()
        new_password = request.form.get('password', '').strip()

        if not re.match(r'[^@]+@[^@]+\.[^@]+', new_email):
            flash('Invalid email address!', 'danger')
            return redirect(url_for('edit_profile'))

        if not re.match(r'^[A-Za-z0-9]+$', new_username):
            flash('Username must contain only characters and numbers!', 'danger')
            return redirect(url_for('edit_profile'))

        cursor.execute(
            "SELECT id FROM users WHERE (username = %s OR email = %s) AND id != %s",
            (new_username, new_email, user['id'])
        )
        existing = cursor.fetchone()
        if existing:
            flash('Username or email already taken by another account.', 'danger')
            return redirect(url_for('edit_profile'))

        if new_password:
            hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')
            cursor.execute(
                "UPDATE users SET username = %s, email = %s, password = %s WHERE id = %s",
                (new_username, new_email, hashed_pw, user['id'])
            )
        else:
            cursor.execute(
                "UPDATE users SET username = %s, email = %s WHERE id = %s",
                (new_username, new_email, user['id'])
            )

        mysql.connection.commit()
        session['username'] = new_username
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('user_dashboard'))

    return render_template('edit_profile.html', user=user)


# ---------- Run ----------
if __name__ == '__main__':
    app.run(debug=True)
