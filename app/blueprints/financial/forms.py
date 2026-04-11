from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, FloatField, SelectField, TextAreaField,
                     SubmitField, IntegerField)
from wtforms.validators import DataRequired, Optional, NumberRange


class TransactionForm(FlaskForm):
    type = SelectField('Type', choices=[('income', 'Income'), ('expense', 'Expense')],
                       validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    payee = StringField('Payee', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    category = StringField('Category', validators=[Optional()])
    payment_method = SelectField('Payment Method', choices=[
        ('cash', 'Cash'), ('card', 'Card'), ('transfer', 'Transfer'), ('check', 'Check'),
    ])
    location_id = SelectField('Location', coerce=int, validators=[DataRequired()])
    receipt = FileField('Receipt', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDFs only!')
    ])
    submit = SubmitField('Save')


class VoidForm(FlaskForm):
    reason = TextAreaField('Reason for Void', validators=[DataRequired()])
    approved_by = SelectField('Supervisor Approval', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Confirm Void')


class CloseoutForm(FlaskForm):
    location_id = SelectField('Location', coerce=int, validators=[DataRequired()])
    month = IntegerField('Month', validators=[DataRequired(), NumberRange(min=1, max=12)])
    year = IntegerField('Year', validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    submit = SubmitField('Close Month')


class ImportForm(FlaskForm):
    file = FileField('CSV or Excel File', validators=[DataRequired()])
    submit = SubmitField('Upload & Preview')
