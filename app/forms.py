from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FloatField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, ValidationError, Optional

class SignupForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters"),
    ])
    submit = SubmitField('Sign Up')

    def validate_password(self, field):
        if not any(c.isupper() for c in field.data):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not any(c.isdigit() for c in field.data):
            raise ValidationError('Password must contain at least one number')
        if not any(c in '!@#$%^&*' for c in field.data):
            raise ValidationError('Password must contain at least one special character (!@#$%^&*)')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

class CarbonEntryForm(FlaskForm):
    activity_category = SelectField('Activity Category', choices=[
        ('transport', 'Transport'),
        ('food', 'Food & Diet'),
        ('energy', 'Energy Usage')
    ])
    transport_type = SelectField('Transport Type', choices=[
        ('car', 'Car'),
        ('bus', 'Bus'),
        ('train', 'Train'),
        ('bike', 'Bicycle'),
        ('walk', 'Walking'),
        ('flight', 'Flight')
    ], validators=[Optional()])
    distance = FloatField('Distance (km)', validators=[Optional()])
    fuel_type = SelectField('Fuel Type', choices=[
        ('petrol', 'Petrol / Gasoline'),
        ('diesel', 'Diesel')
    ], validators=[Optional()])
    fuel_liters = FloatField('Fuel Used (Liters)', validators=[Optional()])
    energy_usage = FloatField('Energy Usage (kWh)', validators=[Optional()])
    diet_type = SelectField('Diet Type', choices=[
        ('meat', 'Meat Heavy'),
        ('mixed', 'Mixed Diet'),
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan')
    ], validators=[Optional()])
    custom_activity = TextAreaField('Custom Activity Description')
    submit = SubmitField('Log Activity')
