from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, PasswordField, SubmitField,EmailField
from wtforms.validators import DataRequired, Email, Length, ValidationError
import re



def has_number(form,field):
    if not re.search(r"\d",field.data):
        raise ValidationError("Password must contain at least one number.")
    
def has_symbol(form,field):
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", field.data):
        raise ValidationError("Password must contain at least one symbol")

def no_number(form,field):
    if  re.search(r"\d",field.data):
        raise ValidationError("Field must not have any numbers")
    
def no_symbol(form,field):
    if  re.search(r"[!@#$%^&*(),.?\":{}|<>]", field.data):
        raise ValidationError("Field must not contain any symbols")





class SignupForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(),Length(min=5)])
    email = EmailField("Email", validators=[DataRequired(),Email()])
    password = PasswordField("Password", validators=[DataRequired(),Length(min=6,message="At least 6 characters"),has_number,has_symbol])
    firstname = StringField("First Name", validators=[DataRequired(),no_number,no_symbol])
    lastname = StringField("Last Name", validators=[DataRequired(), no_number,no_symbol])
    submit = SubmitField("Sign Up")

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])


