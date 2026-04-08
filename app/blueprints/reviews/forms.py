from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from wtforms import TextAreaField, SelectField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Optional, NumberRange


class ReviewForm(FlaskForm):
    content = TextAreaField('Review', validators=[DataRequired()])
    coach_id = SelectField('Coach (optional)', coerce=int, validators=[Optional()])
    location_id = SelectField('Location', coerce=int, validators=[DataRequired()])
    images = MultipleFileField('Supporting Images', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])
    submit = SubmitField('Submit Review')


class DisputeForm(FlaskForm):
    statement = TextAreaField('Dispute Statement', validators=[DataRequired()])
    evidence = MultipleFileField('Evidence Files', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDFs only!')
    ])
    submit = SubmitField('Submit Dispute')


class ArbitrationForm(FlaskForm):
    outcome = TextAreaField('Arbitration Outcome', validators=[DataRequired()])
    submit = SubmitField('Record Outcome')


class ReportForm(FlaskForm):
    reason = TextAreaField('Reason', validators=[DataRequired()])
    submit = SubmitField('Report')
