from flask import Blueprint

bp = Blueprint('moderation', __name__)

from app.blueprints.moderation import routes  # noqa: E402, F401
