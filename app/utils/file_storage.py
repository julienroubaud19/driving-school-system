import hashlib
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


def save_file_with_tracking(file_obj, category, resource_type, resource_id, user_id):
    if not file_obj or not file_obj.filename:
        return None, None

    if not allowed_file(file_obj.filename):
        return None, None

    file_data = file_obj.read()
    file_hash = hashlib.sha256(file_data).hexdigest()
    file_size = len(file_data)
    file_obj.seek(0)

    from app.extensions import db
    from app.models.attachment import Attachment

    existing = Attachment.find_by_hash(file_hash, resource_type)

    ext = file_obj.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    safe_name = secure_filename(unique_name)

    dest_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], category)
    os.makedirs(dest_dir, exist_ok=True)
    filepath = os.path.join(dest_dir, safe_name)
    file_obj.save(filepath)

    relative_path = os.path.join(category, safe_name)

    previous = Attachment.query.filter_by(
        resource_type=resource_type, resource_id=resource_id
    ).order_by(Attachment.version.desc()).first()

    attachment = Attachment(
        filename=file_obj.filename,
        file_path=relative_path,
        file_hash=file_hash,
        file_size=file_size,
        content_type=category,
        resource_type=resource_type,
        resource_id=resource_id,
        version=(previous.version + 1) if previous else 1,
        parent_id=previous.id if previous else None,
        uploaded_by=user_id,
        is_duplicate=existing is not None,
        duplicate_of_id=existing.id if existing else None,
    )
    db.session.add(attachment)

    return relative_path, attachment


def get_path(relative_path):
    if not relative_path:
        return None
    return os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)


def delete_file(relative_path):
    full = get_path(relative_path)
    if full and os.path.exists(full):
        os.remove(full)
