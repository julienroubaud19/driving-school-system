from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.moderation import ModerationQueue, ModerationLog, SensitiveWord, UserBlacklist
from app.models.review import Review


def check_content(text, content_type, content_id, user_id):
    reasons = []
    flagged_words = []

    bl = UserBlacklist.query.filter(
        UserBlacklist.user_id == user_id,
        (UserBlacklist.expires_at.is_(None)) | (UserBlacklist.expires_at > datetime.now(timezone.utc)),
    ).first()
    if bl:
        reasons.append('blacklist')

    words = SensitiveWord.query.filter_by(is_active=True).all()
    text_lower = text.lower()
    for w in words:
        if w.word.lower() in text_lower:
            flagged_words.append(w.word)
    if flagged_words:
        reasons.append('auto_word_match')

    if content_type == 'review':
        rate_limit = current_app.config.get('REVIEW_RATE_LIMIT', 3)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = Review.query.filter(
            Review.created_by == user_id,
            Review.created_at >= one_hour_ago,
        ).count()
        if recent >= rate_limit:
            reasons.append('rate_limit')

    if reasons:
        item = ModerationQueue(
            content_type=content_type,
            content_id=content_id,
            reason=','.join(reasons),
            flagged_words=','.join(flagged_words) if flagged_words else None,
        )
        db.session.add(item)
        db.session.commit()
        return item

    return None


def approve_content(queue_id, moderator_id, notes=None):
    item = db.session.get(ModerationQueue, queue_id)
    if not item:
        return None
    item.status = 'approved'
    item.handled_by = moderator_id
    item.handled_at = datetime.now(timezone.utc)

    log = ModerationLog(
        queue_id=queue_id, action='approved',
        performed_by=moderator_id, notes=notes,
    )
    db.session.add(log)

    if item.content_type == 'review':
        review = db.session.get(Review, item.content_id)
        if review:
            review.status = 'approved'

    db.session.commit()
    return item


def reject_content(queue_id, moderator_id, notes=None):
    item = db.session.get(ModerationQueue, queue_id)
    if not item:
        return None
    item.status = 'rejected'
    item.handled_by = moderator_id
    item.handled_at = datetime.now(timezone.utc)

    log = ModerationLog(
        queue_id=queue_id, action='rejected',
        performed_by=moderator_id, notes=notes,
    )
    db.session.add(log)

    if item.content_type == 'review':
        review = db.session.get(Review, item.content_id)
        if review:
            review.status = 'rejected'

    db.session.commit()
    return item
