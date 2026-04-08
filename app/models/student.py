from datetime import datetime, timezone

from app.extensions import db


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    date_of_birth = db.Column(db.Date, nullable=True)
    address = db.Column(db.String(300))
    license_number = db.Column(db.String(50))
    enrollment_date = db.Column(db.Date, default=lambda: datetime.now(timezone.utc).date())
    status = db.Column(db.String(20), default='enrolled')  # enrolled/active/completed/withdrawn
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    assigned_coach_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    handler_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    location = db.relationship('Location', backref='students')
    assigned_coach = db.relationship('User', foreign_keys=[assigned_coach_id], backref='coached_students')
    handler = db.relationship('User', foreign_keys=[handler_id], backref='handled_students')
    notes = db.relationship('StudentNote', backref='student', lazy='dynamic',
                            order_by='StudentNote.created_at.desc()')

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def __repr__(self):
        return f'<Student {self.full_name}>'


class StudentNote(db.Model):
    __tablename__ = 'student_notes'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    coach_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    coach = db.relationship('User', backref='student_notes')
