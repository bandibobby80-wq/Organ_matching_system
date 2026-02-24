from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'organ_matching_system_secret_key_2025'

# Data storage files
USERS_FILE = 'data/users.json'
MATCHES_FILE = 'data/matches.json'
DATA_DIR = 'data'

# Ensure data directory exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    with open(USERS_FILE, 'w') as f:
        json.dump({}, f)
    with open(MATCHES_FILE, 'w') as f:
        json.dump([], f)

# Default admin credentials
DEFAULT_ADMIN = {
    'username': 'admin',
    'password': generate_password_hash('admin123'),
    'role': 'admin',
    'email': 'admin@organsystem.com',
    'name': 'System Administrator'
}

# Initialize default admin
def init_admin():
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        if 'admin' not in users:
            users['admin'] = DEFAULT_ADMIN
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=4)
    except:
        pass

init_admin()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['role'] != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['role'] not in ['doctor', 'admin']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Load users from JSON
def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

# Save users to JSON
def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# Load matches from JSON
def load_matches():
    try:
        with open(MATCHES_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

# Save matches to JSON
def save_matches(matches):
    with open(MATCHES_FILE, 'w') as f:
        json.dump(matches, f, indent=4)

# Calculate organ match percentage
def calculate_match_percentage(donor, patient):
    match_score = 0
    total_score = 100

    # Blood group match (30 points)
    if donor['blood_group'] == patient['blood_group']:
        match_score += 30
    elif (donor['blood_group'] == 'O' or patient['blood_group'] == 'AB'):
        match_score += 15

    # HLA match (35 points)
    donor_hla = set(donor.get('hla', '').split(','))
    patient_hla = set(patient.get('hla', '').split(','))
    hla_match = len(donor_hla & patient_hla) / max(len(donor_hla | patient_hla), 1)
    match_score += hla_match * 35

    # Age compatibility (20 points)
    age_diff = abs(int(donor['age']) - int(patient['age']))
    if age_diff <= 10:
        match_score += 20
    elif age_diff <= 20:
        match_score += 15
    elif age_diff <= 30:
        match_score += 10
    else:
        match_score += 5

    # Tissue type match (15 points)
    if donor.get('tissue_type') == patient.get('tissue_type'):
        match_score += 15
    else:
        match_score += 7

    match_percentage = round((match_score / total_score) * 100, 2)
    suitable = match_percentage >= 60

    return {
        'percentage': match_percentage,
        'suitable': suitable,
        'blood_match': 'Yes' if donor['blood_group'] == patient['blood_group'] else 'Partial',
        'hla_match': round(hla_match * 100, 2)
    }

@app.route('/')
def index():
    if 'user' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['role'] == 'doctor':
            return redirect(url_for('doctor_dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        email = request.form.get('email')
        name = request.form.get('name')
        role = request.form.get('role', 'doctor')  # Get role from form

        users = load_users()

        # Validate role
        if not role or role not in ['doctor', 'admin']:
            return render_template('register.html', error='Invalid role selected')

        if username in users:
            return render_template('register.html', error='Username already exists')

        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')

        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters')

        users[username] = {
            'username': username,
            'password': generate_password_hash(password),
            'email': email,
            'name': name,
            'role': role,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        save_users(users)
        return redirect(url_for('login', success='Registration successful. Please login.'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        users = load_users()

        if username in users and check_password_hash(users[username]['password'], password):
            session['user'] = username
            session['role'] = users[username]['role']
            session['name'] = users[username]['name']

            # Redirect based on role
            if users[username]['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif users[username]['role'] == 'doctor':
                return redirect(url_for('doctor_dashboard'))
        else:
            return render_template('login.html', error='Invalid username or password')

    success = request.args.get('success')
    return render_template('login.html', success=success)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/doctor-dashboard')
@doctor_required
def doctor_dashboard():
    matches = load_matches()
    return render_template('doctor_dashboard.html', 
                         name=session.get('name'),
                         role=session.get('role'),
                         matches=matches)

@app.route('/calculate-match', methods=['POST'])
@doctor_required
def calculate_match():
    data = request.json

    donor = {
        'name': data.get('donor_name'),
        'age': data.get('donor_age'),
        'blood_group': data.get('donor_blood'),
        'hla': data.get('donor_hla'),
        'tissue_type': data.get('donor_tissue'),
        'height': data.get('donor_height'),
        'weight': data.get('donor_weight')
    }

    patient = {
        'name': data.get('patient_name'),
        'age': data.get('patient_age'),
        'blood_group': data.get('patient_blood'),
        'hla': data.get('patient_hla'),
        'tissue_type': data.get('patient_tissue'),
        'height': data.get('patient_height'),
        'weight': data.get('patient_weight')
    }

    result = calculate_match_percentage(donor, patient)

    # Save to matches history
    matches = load_matches()
    match_record = {
        'id': len(matches) + 1,
        'doctor': session.get('name'),
        'donor_name': donor['name'],
        'patient_name': patient['name'],
        'match_percentage': result['percentage'],
        'suitable': result['suitable'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'donor': donor,
        'patient': patient,
        'details': result
    }
    matches.append(match_record)
    save_matches(matches)

    return jsonify({
        'success': True,
        'data': result,
        'donor': donor,
        'patient': patient
    })

@app.route('/admin-dashboard')
@admin_required
def admin_dashboard():
    users = load_users()
    doctors = {k: v for k, v in users.items() if v['role'] == 'doctor'}
    matches = load_matches()

    return render_template('admin_dashboard.html',
                         name=session.get('name'),
                         role=session.get('role'),
                         doctors=doctors,
                         matches=matches,
                         total_doctors=len(doctors),
                         total_matches=len(matches))

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    users = load_users()
    doctors = {k: v for k, v in users.items() if v['role'] == 'doctor'}
    return jsonify(doctors)

@app.route('/api/users/add', methods=['POST'])
@admin_required
def add_user():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    name = data.get('name')
    role = data.get('role', 'doctor')
    password = data.get('password', 'doctor123')

    users = load_users()

    if not role or role not in ['doctor', 'admin']:
        return jsonify({'success': False, 'error': 'Invalid role'}), 400

    if username in users:
        return jsonify({'success': False, 'error': 'Username already exists'}), 400

    users[username] = {
        'username': username,
        'password': generate_password_hash(password),
        'email': email,
        'name': name,
        'role': role,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    save_users(users)
    return jsonify({'success': True, 'message': 'User added successfully'})

@app.route('/api/users/update', methods=['POST'])
@admin_required
def update_user():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    name = data.get('name')
    role = data.get('role')

    users = load_users()

    if username not in users:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    users[username]['email'] = email
    users[username]['name'] = name
    if role and role in ['doctor', 'admin']:
        users[username]['role'] = role

    save_users(users)
    return jsonify({'success': True, 'message': 'User updated successfully'})

@app.route('/api/users/delete/<username>', methods=['DELETE'])
@admin_required
def delete_user(username):
    if username == 'admin':
        return jsonify({'success': False, 'error': 'Cannot delete admin user'}), 400

    users = load_users()

    if username not in users:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    del users[username]
    save_users(users)

    return jsonify({'success': True, 'message': 'User deleted successfully'})

@app.route('/api/matches', methods=['GET'])
@admin_required
def get_matches():
    matches = load_matches()
    return jsonify(matches)

@app.route('/api/matches/update/<int:match_id>', methods=['POST'])
@admin_required
def update_match(match_id):
    data = request.json
    matches = load_matches()

    for match in matches:
        if match['id'] == match_id:
            match['donor_name'] = data.get('donor_name', match['donor_name'])
            match['patient_name'] = data.get('patient_name', match['patient_name'])
            match['suitable'] = data.get('suitable', match['suitable'])
            match['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_matches(matches)
            return jsonify({'success': True, 'message': 'Match updated successfully'})

    return jsonify({'success': False, 'error': 'Match not found'}), 404

@app.route('/api/matches/delete/<int:match_id>', methods=['DELETE'])
@admin_required
def delete_match(match_id):
    matches = load_matches()
    matches = [m for m in matches if m['id'] != match_id]
    save_matches(matches)
    return jsonify({'success': True, 'message': 'Match deleted successfully'})

if __name__ == '__main__':
    app.run(debug=True)
