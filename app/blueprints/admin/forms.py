from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length


class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[Optional(), Length(min=12)])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    location_id = SelectField('Location', coerce=int, validators=[Optional()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save')


class LocationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    address = StringField('Address', validators=[Optional()])
    phone = StringField('Phone', validators=[Optional()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save')


class RatingDimensionForm(FlaskForm):
    name = StringField('Name (code)', validators=[DataRequired()])
    label = StringField('Display Label', validators=[DataRequired()])
    sort_order = StringField('Sort Order', validators=[Optional()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save')
