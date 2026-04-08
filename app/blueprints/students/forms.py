from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Optional


class StudentForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    phone = StringField('Phone', validators=[Optional()])
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    address = TextAreaField('Address', validators=[Optional()])
    license_number = StringField('License Number', validators=[Optional()])
    status = SelectField('Status', choices=[
        ('enrolled', 'Enrolled'), ('active', 'Active'),
        ('completed', 'Completed'), ('withdrawn', 'Withdrawn'),
    ])
    location_id = SelectField('Location', coerce=int, validators=[DataRequired()])
    assigned_coach_id = SelectField('Assigned Coach', coerce=int, validators=[Optional()])
    submit = SubmitField('Save')


class StudentNoteForm(FlaskForm):
    content = TextAreaField('Note', validators=[DataRequired()])
    submit = SubmitField('Add Note')
