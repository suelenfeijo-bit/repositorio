from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, Length, NumberRange, ValidationError


class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[Length(min=1, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("Register")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class ProductForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(min=2, max=200)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10, max=5000)])
    price_cents = IntegerField("Price (cents)", validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField("Save")


class ReviewForm(FlaskForm):
    rating = IntegerField("Rating", validators=[DataRequired(), NumberRange(min=1, max=5)])
    comment = TextAreaField("Comment", validators=[DataRequired(), Length(min=10, max=2000)])
    submit = SubmitField("Submit Review")