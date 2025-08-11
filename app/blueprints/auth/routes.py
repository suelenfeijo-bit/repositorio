from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError

from app.forms import RegisterForm, LoginForm
from app.models import db, User
from app import csrf

auth_bp = Blueprint("auth", __name__, template_folder="../../templates/auth")

oauth = OAuth()

def _register_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config.get('OAUTH_GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('OAUTH_GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )


@auth_bp.record
def on_load(setup_state):
    app = setup_state.app
    _register_oauth(app)


@auth_bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    return render_template("auth/login.html", form=form)


@auth_bp.post("/login")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        flash("Invalid credentials", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=form.email.data.lower()).first()
    if not user or not user.check_password(form.password.data):
        flash("Invalid credentials", "danger")
        return redirect(url_for("auth.login"))

    login_user(user)
    flash("Welcome back!", "success")
    return redirect(url_for("index"))


@auth_bp.get("/register")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegisterForm()
    return render_template("auth/register.html", form=form)


@auth_bp.post("/register")
def register_post():
    form = RegisterForm()
    if not form.validate_on_submit():
        flash("Invalid data", "danger")
        return redirect(url_for("auth.register"))
    user = User(email=form.email.data.lower(), name=form.name.data)
    user.set_password(form.password.data)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Email already registered", "warning")
        return redirect(url_for("auth.register"))

    login_user(user)
    flash("Account created", "success")
    return redirect(url_for("index"))


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("index"))


@auth_bp.get('/oauth/google')
def oauth_google():
    redirect_uri = current_app.config.get('OAUTH_REDIRECT_URI') or url_for('auth.oauth_google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.get('/oauth/google/callback')
def oauth_google_callback():
    token = oauth.google.authorize_access_token()
    userinfo = token.get('userinfo') or oauth.google.parse_id_token(token)
    if not userinfo:
        flash("OAuth failed", "danger")
        return redirect(url_for('auth.login'))

    email = userinfo.get('email')
    sub = userinfo.get('sub')
    name = userinfo.get('name')

    user = User.query.filter_by(oauth_provider='google', oauth_sub=sub).first()
    if not user:
        user = User.query.filter_by(email=email.lower()).first()
        if user:
            user.oauth_provider = 'google'
            user.oauth_sub = sub
        else:
            user = User(email=email.lower(), name=name, oauth_provider='google', oauth_sub=sub)
            user.password_hash = None
        db.session.add(user)
        db.session.commit()

    login_user(user)
    flash("Logged in with Google", "success")
    return redirect(url_for('index'))


@auth_bp.post('/token')
@csrf.exempt
def issue_jwt():
    # Exchange email/password for JWT access token
    form = LoginForm()
    if not form.validate_on_submit():
        return {"msg": "invalid credentials"}, 400
    user = User.query.filter_by(email=form.email.data.lower()).first()
    if not user or not user.check_password(form.password.data):
        return {"msg": "invalid credentials"}, 401
    access_token = create_access_token(identity=str(user.id))
    return {"access_token": access_token}