from flask import Blueprint

bp = Blueprint('reviews', __name__)

from app.blueprints.reviews import routes  # noqa: E402, F401
