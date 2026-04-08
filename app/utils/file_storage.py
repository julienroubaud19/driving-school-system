import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename


def allowed_file(filename):
    allowed = current_app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_file(file_obj, category='receipts'):
    if not file_obj or not file_obj.filename:
        return None

    if not allowed_file(file_obj.filename):
        return None

    ext = file_obj.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    safe_name = secure_filename(unique_name)

    dest_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], category)
    os.makedirs(dest_dir, exist_ok=True)

    filepath = os.path.join(dest_dir, safe_name)
    file_obj.save(filepath)
    return os.path.join(category, safe_name)


def get_path(relative_path):
    if not relative_path:
        return None
    return os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)


def delete_file(relative_path):
    full = get_path(relative_path)
    if full and os.path.exists(full):
        os.remove(full)
