import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'driving_school.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}

    # Auth
    SESSION_TIMEOUT_MINUTES = 30
    LOGIN_LOCKOUT_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15
    PASSWORD_MIN_LENGTH = 12

    # Rate limits
    NOTIFICATION_RATE_LIMIT = 5   # per user per hour
    REVIEW_RATE_LIMIT = 3         # per user per hour

    # Deduplication
    DUPLICATE_SIMILARITY_THRESHOLD = 0.92

    # Moderation
    MODERATION_WORD_LIST_PATH = os.path.join(BASE_DIR, 'config_data', 'sensitive_words.txt')
    MODERATION_BLACKLIST_PATH = os.path.join(BASE_DIR, 'config_data', 'blacklist.txt')


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = '/tmp/test_uploads'
    LOGIN_LOCKOUT_MINUTES = 15
