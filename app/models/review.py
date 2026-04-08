from datetime import datetime, timezone

from app.extensions import db


class RatingDimension(db.Model):
    __tablename__ = 'rating_dimensions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    label = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    coach_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected/disputed
    moderation_note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    student = db.relationship('Student', backref='reviews')
    coach = db.relationship('User', foreign_keys=[coach_id], backref='coach_reviews')
    author = db.relationship('User', foreign_keys=[created_by], backref='authored_reviews')
    location = db.relationship('Location', backref='reviews')
    scores = db.relationship('RatingScore', backref='review', cascade='all, delete-orphan')
    images = db.relationship('ReviewImage', backref='review', cascade='all, delete-orphan')
    likes = db.relationship('ReviewLike', backref='review', cascade='all, delete-orphan')
    reports = db.relationship('ReviewReport', backref='review', cascade='all, delete-orphan')
    disputes = db.relationship('Dispute', backref='review', cascade='all, delete-orphan')

    @property
    def like_count(self):
        return len(self.likes)

    @property
    def average_score(self):
        if not self.scores:
            return 0
        return sum(s.score for s in self.scores) / len(self.scores)


class RatingScore(db.Model):
    __tablename__ = 'rating_scores'

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    dimension_id = db.Column(db.Integer, db.ForeignKey('rating_dimensions.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)  # 1-5

    dimension = db.relationship('RatingDimension')

    __table_args__ = (
        db.CheckConstraint('score >= 1 AND score <= 5', name='ck_score_range'),
    )


class ReviewImage(db.Model):
    __tablename__ = 'review_images'

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ReviewLike(db.Model):
    __tablename__ = 'review_likes'

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint('review_id', 'user_id', name='uq_review_like_user'),
    )


class ReviewReport(db.Model):
    __tablename__ = 'review_reports'

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    reported_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending/reviewed/dismissed
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    reporter = db.relationship('User', foreign_keys=[reported_by])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])


class Dispute(db.Model):
    __tablename__ = 'disputes'

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    initiated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    statement = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')  # open/under_review/resolved
    arbitration_outcome = db.Column(db.Text)
    arbitrated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    initiator = db.relationship('User', foreign_keys=[initiated_by])
    arbitrator = db.relationship('User', foreign_keys=[arbitrated_by])
    evidence = db.relationship('DisputeEvidence', backref='dispute', cascade='all, delete-orphan')


class DisputeEvidence(db.Model):
    __tablename__ = 'dispute_evidence'

    id = db.Column(db.Integer, primary_key=True)
    dispute_id = db.Column(db.Integer, db.ForeignKey('disputes.id'), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    uploader = db.relationship('User')
