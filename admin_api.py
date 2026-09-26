import os
import json
import hashlib
import secrets
import time
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, session

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ===== CONFIGURATION =====
UPLOAD_DIR = '/var/www/drghosh'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Admin credentials (change these!)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = hashlib.sha256('drghosh@2026'.encode()).hexdigest()

DATA_FILE = os.path.join(os.path.dirname(__file__), 'site_data.json')

# ===== DEFAULT SITE DATA =====
DEFAULT_DATA = {
    "doctor_name_en": "Dr. Debabrata Ghosh",
    "doctor_name_bn": "ডা. দেবব্রত ঘোষ",
    "title_bn": "নেফ্রোলজিস্ট ও কিডনি রোগ বিশেষজ্ঞ",
    "qualifications": "MBBS (SHSMC) | MD (Nephrology, BMU) | MACP | CCD",
    "bmdc": "A-70064",
    "experience": "১৩+",
    "position": "সহকারী অধ্যাপক ও পরিচালক (ইনচার্জ)",
    "workplace": "Institute of Nuclear Medicine & Allied Sciences (INMAS), Gopalganj",
    "chamber_name": "মেডিনোভা মেডিক্যাল সার্ভিসেস",
    "chamber_address": "জাকির সুপার মার্কেট, ১৪৫ বঙ্গবন্ধু রোড, চাষাড়া, নারায়ণগঞ্জ - ১৪০০",
    "schedule_days": "মঙ্গলবার থেকে শনিবার",
    "schedule_time": "সন্ধ্যা ৬:০০টা – রাত ১০:০০টা",
    "closed_day": "শুক্রবার বন্ধ",
    "phone_1": "01715-318533",
    "phone_2": "+880 1913-119989",
    "whatsapp": "8801913119989",
    "facebook": "https://www.facebook.com/profile.php?id=61588853776641",
    "gallery_photos": []
}


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_DATA.copy()


def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


def rebuild_index():
    index_path = os.path.join(UPLOAD_DIR, 'index.html')
    if not os.path.exists(index_path):
        return False
    
    with open(index_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Generate gallery HTML
    gallery_html = []
    
    def scan_dir(subdir=''):
        dir_path = os.path.join(UPLOAD_DIR, subdir) if subdir else UPLOAD_DIR
        if not os.path.exists(dir_path):
            return []
        
        images = []
        for f in os.listdir(dir_path):
            if f.lower().endswith(tuple(ALLOWED_EXTENSIONS)):
                stat = os.stat(os.path.join(dir_path, f))
                url = f"{subdir}/{f}" if subdir else f
                images.append({
                    'name': f,
                    'url': url,
                    'modified': stat.st_mtime
                })
        return images
        
    all_images = scan_dir() + scan_dir('gallery')
    all_images.sort(key=lambda x: x['modified'], reverse=True)
    
    for img in all_images:
        url = img['url']
        name = img['name']
        title = os.path.basename(name).rsplit('.', 1)[0].replace('_', ' ').title()
        gallery_html.append(f'''                <div class="resource-card" data-aos="fade-up" onclick="openLightbox('{url}')">
                    <img src="{url}" alt="{name}">
                    <div class="resource-card-overlay">
                        <h4>{title}</h4>
                        <p>Click to view full size</p>
                    </div>
                </div>''')
    
    new_gallery = '\n'.join(gallery_html)
    
    import re
    html = re.sub(
        r'<!-- GALLERY_START -->.*?<!-- GALLERY_END -->',
        f'<!-- GALLERY_START -->\n{new_gallery}\n                <!-- GALLERY_END -->',
        html,
        flags=re.DOTALL
    )
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)
        
    return True

# ===== AUTH ROUTES =====
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    pw_hash = hashlib.sha256(password.encode()).hexdigest()

    if username == ADMIN_USERNAME and pw_hash == ADMIN_PASSWORD_HASH:
        session['logged_in'] = True
        session['login_time'] = time.time()
        return jsonify({'success': True, 'message': 'Login successful'})
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/check-auth')
def check_auth():
    return jsonify({'authenticated': bool(session.get('logged_in'))})


# ===== DATA ROUTES =====
@app.route('/api/data', methods=['GET'])
@login_required
def get_data():
    return jsonify(load_data())


@app.route('/api/data', methods=['POST'])
@login_required
def update_data():
    new_data = request.get_json()
    current = load_data()
    # Only update known fields
    for key in DEFAULT_DATA:
        if key in new_data and key != 'gallery_photos':
            current[key] = new_data[key]
    save_data(current)
    rebuild_index()
    return jsonify({'success': True, 'message': 'Data updated'})

@app.route('/api/rebuild', methods=['POST'])
@login_required
def rebuild_site():
    success = rebuild_index()
    if success:
        return jsonify({'success': True, 'message': 'Site rebuilt'})
    return jsonify({'success': False, 'message': 'Failed to rebuild site'}), 500

# ===== PHOTO ROUTES =====
@app.route('/api/photos', methods=['GET'])
@login_required
def list_photos():
    files = []
    def scan_dir(subdir=''):
        dir_path = os.path.join(UPLOAD_DIR, subdir) if subdir else UPLOAD_DIR
        if not os.path.exists(dir_path):
            return
        
        for f in os.listdir(dir_path):
            if f.lower().endswith(tuple(ALLOWED_EXTENSIONS)):
                filepath = os.path.join(dir_path, f)
                stat = os.stat(filepath)
                url = f"/{subdir}/{f}" if subdir else f"/{f}"
                name = f"{subdir}/{f}" if subdir else f
                files.append({
                    'name': name,
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'url': url
                })
    scan_dir()
    scan_dir('gallery')
    files.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify(files)


@app.route('/api/photos/upload', methods=['POST'])
@login_required
def upload_photo():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    # Check file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large (max 10MB)'}), 400

    # Folder selection
    subfolder = request.form.get('folder', '').strip()
    if subfolder and subfolder == 'gallery':
        dest_dir = os.path.join(UPLOAD_DIR, 'gallery')
        url_prefix = '/gallery/'
        name_prefix = 'gallery/'
    else:
        dest_dir = UPLOAD_DIR
        url_prefix = '/'
        name_prefix = ''

    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    # Generate safe filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    custom_name = request.form.get('custom_name', '').strip()
    if custom_name:
        # Sanitize custom name
        safe_name = ''.join(c for c in custom_name if c.isalnum() or c in '-_').strip()
        if safe_name:
            filename = f'{safe_name}.{ext}'
        else:
            filename = f'photo_{int(time.time())}.{ext}'
    else:
        filename = f'photo_{int(time.time())}.{ext}'

    filepath = os.path.join(dest_dir, filename)

    # Don't overwrite index.html or admin.html
    if filename in ('index.html', 'admin.html'):
        return jsonify({'error': 'Cannot use that filename'}), 400

    file.save(filepath)
    os.chmod(filepath, 0o644)
    rebuild_index()

    return jsonify({
        'success': True,
        'message': f'File "{filename}" uploaded successfully',
        'filename': f'{name_prefix}{filename}',
        'url': f'{url_prefix}{filename}'
    })


@app.route('/api/photos/<path:filename>', methods=['DELETE'])
@login_required
def delete_photo(filename):
    # Prevent deleting critical files
    protected = {'index.html', 'admin.html'}
    if filename in protected:
        return jsonify({'error': 'Cannot delete protected files'}), 403

    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    os.remove(filepath)
    rebuild_index()
    return jsonify({'success': True, 'message': f'"{filename}" deleted'})


# ===== CHANGE PASSWORD =====
@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    global ADMIN_PASSWORD_HASH
    data = request.get_json()
    current = data.get('current_password', '')
    new_pw = data.get('new_password', '')

    if hashlib.sha256(current.encode()).hexdigest() != ADMIN_PASSWORD_HASH:
        return jsonify({'error': 'Current password incorrect'}), 400

    if len(new_pw) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    ADMIN_PASSWORD_HASH = hashlib.sha256(new_pw.encode()).hexdigest()
    return jsonify({'success': True, 'message': 'Password changed'})


if __name__ == '__main__':
    # Initialize data file if not exists
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
    app.run(host='127.0.0.1', port=5000, debug=False)
