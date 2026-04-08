from flask import Blueprint

bp = Blueprint('financial', __name__)

from app.blueprints.financial import routes  # noqa: E402, F401
