from __future__ import annotations
import os
from datetime import datetime
from difflib import SequenceMatcher

from flask import Flask, render_template_string, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, Length, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash
from flask_talisman import Talisman

# ----------------------------------------------------------------------------
# App + Config
# ----------------------------------------------------------------------------
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "dev-key"),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///single.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

# Relax HTTPS forcing for local dev
Talisman(app, content_security_policy={'default-src': ["'self'"]}, force_https=False)

# ----------------------------------------------------------------------------
# Extensions
# ----------------------------------------------------------------------------
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
csrf = CSRFProtect(app)

# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), default="usd")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(50), default="pending")
    total_cents = db.Column(db.Integer, default=0)
    currency = db.Column(db.String(10), default="usd")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price_cents = db.Column(db.Integer, nullable=False)


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


# ----------------------------------------------------------------------------
# Forms
# ----------------------------------------------------------------------------
class RegisterForm(FlaskForm):
    name = StringField("Nome", validators=[Length(min=1, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=6, max=128)])
    submit = SubmitField("Cadastrar")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Senha", validators=[DataRequired()])
    submit = SubmitField("Entrar")


class ProductForm(FlaskForm):
    name = StringField("Nome", validators=[DataRequired(), Length(min=2, max=200)])
    description = TextAreaField("Descrição", validators=[DataRequired(), Length(min=10, max=5000)])
    price_cents = IntegerField("Preço (centavos)", validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField("Salvar")


class ReviewForm(FlaskForm):
    rating = IntegerField("Nota", validators=[DataRequired(), NumberRange(min=1, max=5)])
    comment = TextAreaField("Comentário", validators=[DataRequired(), Length(min=10, max=2000)])
    submit = SubmitField("Enviar avaliação")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
BASE_HTML = """
<!doctype html>
<title>Marketplace</title>
<nav>
  <a href="{{ url_for('index') }}">Início</a>
  <a href="{{ url_for('list_products') }}">Produtos</a>
  <a href="{{ url_for('view_cart') }}">Carrinho</a>
  {% if current_user.is_authenticated %}
    <form action="{{ url_for('logout') }}" method="post" style="display:inline;">
      {{ csrf_token() }}
      <button type="submit">Sair</button>
    </form>
  {% else %}
    <a href="{{ url_for('login') }}">Entrar</a>
    <a href="{{ url_for('register') }}">Cadastrar</a>
  {% endif %}
</nav>
<hr>
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <ul>
    {% for cat, msg in messages %}
      <li>{{ msg }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
{% block content %}{% endblock %}
"""


def get_cart():
    return session.setdefault('cart', {})


def save_cart(cart):
    session['cart'] = cart
    session.modified = True


def user_purchased_product(user_id: int, product_id: int) -> bool:
    q = db.session.execute(
        db.select(OrderItem).join(Order, OrderItem.order_id == Order.id)
        .where(Order.user_id == user_id, Order.status == 'paid', OrderItem.product_id == product_id)
    ).first()
    return q is not None


def is_similar_text(a: str, b: str) -> bool:
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio() > 0.9


# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------
@app.get("/")
def index():
    products = Product.query.filter_by(active=True).order_by(Product.created_at.desc()).limit(8).all()
    return render_template_string(
        BASE_HTML + """
        {% block content %}
        <h1>Marketplace</h1>
        {% for p in products %}
          <div>
            <a href="{{ url_for('product_detail', product_id=p.id) }}">{{ p.name }}</a>
            <span> - {{ (p.price_cents/100)|round(2) }} {{ p.currency|upper }}</span>
          </div>
        {% else %}
          <p>Sem produtos.</p>
        {% endfor %}
        {% endblock %}
        """,
        products=products,
    )


@app.get("/register")
def register():
    form = RegisterForm()
    return render_template_string(
        BASE_HTML + """
        {% block content %}
        <h2>Cadastrar</h2>
        <form method="post" action="{{ url_for('register_post') }}">
          {{ form.csrf_token }}
          {{ form.name.label }} {{ form.name(size=32) }}<br>
          {{ form.email.label }} {{ form.email(size=32) }}<br>
          {{ form.password.label }} {{ form.password(size=32) }}<br>
          {{ form.submit() }}
        </form>
        {% endblock %}
        """,
        form=form,
    )


@app.post("/register")
def register_post():
    form = RegisterForm()
    if not form.validate_on_submit():
        flash("Dados inválidos", "danger")
        return redirect(url_for("register"))
    if User.query.filter_by(email=form.email.data.lower()).first():
        flash("Email já cadastrado", "warning")
        return redirect(url_for("register"))
    user = User(email=form.email.data.lower(), name=form.name.data)
    user.set_password(form.password.data)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    flash("Conta criada", "success")
    return redirect(url_for("index"))


@app.get("/login")
def login():
    form = LoginForm()
    return render_template_string(
        BASE_HTML + """
        {% block content %}
        <h2>Entrar</h2>
        <form method="post" action="{{ url_for('login_post') }}">
          {{ form.csrf_token }}
          {{ form.email.label }} {{ form.email(size=32) }}<br>
          {{ form.password.label }} {{ form.password(size=32) }}<br>
          {{ form.submit() }}
        </form>
        {% endblock %}
        """,
        form=form,
    )


@app.post("/login")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        flash("Credenciais inválidas", "danger")
        return redirect(url_for("login"))
    user = User.query.filter_by(email=form.email.data.lower()).first()
    if not user or not user.check_password(form.password.data):
        flash("Credenciais inválidas", "danger")
        return redirect(url_for("login"))
    login_user(user)
    flash("Bem-vindo!", "success")
    return redirect(url_for("index"))


@app.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada", "info")
    return redirect(url_for("index"))


@app.get("/products/")
def list_products():
    products = Product.query.filter_by(active=True).order_by(Product.created_at.desc()).all()
    return render_template_string(
        BASE_HTML + """
        {% block content %}
        <h2>Produtos</h2>
        {% for p in products %}
          <div><a href="{{ url_for('product_detail', product_id=p.id) }}">{{ p.name }}</a></div>
        {% endfor %}
        {% endblock %}
        """,
        products=products,
    )


@app.get("/products/<int:product_id>")
def product_detail(product_id: int):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        flash("Produto não encontrado", "warning")
        return redirect(url_for("list_products"))
    return render_template_string(
        BASE_HTML + """
        {% block content %}
        <h2>{{ product.name }}</h2>
        <p>{{ product.description }}</p>
        <p>Preço: {{ (product.price_cents/100)|round(2) }} {{ product.currency|upper }}</p>
        <form method="post" action="{{ url_for('add_to_cart', product_id=product.id) }}">
          {{ csrf_token() }}
          <button type="submit">Adicionar ao carrinho</button>
        </form>

        <h3>Avaliações</h3>
        <ul>
          {% for r in reviews %}
            <li>{{ r.rating }}/5 - {{ r.comment }}</li>
          {% else %}
            <li>Sem avaliações.</li>
          {% endfor %}
        </ul>

        {% if current_user.is_authenticated %}
          <h4>Escrever uma avaliação</h4>
          <form method="post" action="{{ url_for('create_review', product_id=product.id) }}">
            {{ csrf_token() }}
            <label>Nota</label>
            <input type="number" name="rating" min="1" max="5" required>
            <br>
            <label>Comentário</label>
            <textarea name="comment" required></textarea>
            <br>
            <button type="submit">Enviar</button>
          </form>
        {% else %}
          <p>Entre para avaliar.</p>
        {% endif %}
        {% endblock %}
        """,
        product=product,
        reviews=Review.query.filter_by(product_id=product.id, is_approved=True).order_by(Review.created_at.desc()).all(),
    )


@app.post("/checkout/cart/add/<int:product_id>")
def add_to_cart(product_id: int):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        flash("Produto não encontrado", "warning")
        return redirect(url_for('list_products'))
    cart = get_cart()
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    save_cart(cart)
    flash('Adicionado ao carrinho', 'success')
    return redirect(url_for('product_detail', product_id=product_id))


@app.get("/checkout/cart")
def view_cart():
    cart = get_cart()
    product_ids = [int(pid) for pid in cart.keys()]
    products = Product.query.filter(Product.id.in_(product_ids)).all() if product_ids else []
    items = []
    total_cents = 0
    for product in products:
        quantity = int(cart.get(str(product.id), 0))
        line_total = product.price_cents * quantity
        total_cents += line_total
        items.append({"product": product, "quantity": quantity, "line_total": line_total})
    return render_template_string(
        BASE_HTML + """
        {% block content %}
        <h2>Carrinho</h2>
        <ul>
          {% for item in items %}
            <li>{{ item.product.name }} x {{ item.quantity }} = {{ (item.line_total/100)|round(2) }} {{ item.product.currency|upper }}</li>
          {% endfor %}
        </ul>
        <p>Total: {{ (total_cents/100)|round(2) }}</p>
        {% if current_user.is_authenticated %}
        <form method="post" action="{{ url_for('create_order') }}">
          {{ csrf_token() }}
          <button type="submit">Finalizar (simulado)</button>
        </form>
        {% else %}
          <p>Entre para finalizar a compra.</p>
        {% endif %}
        {% endblock %}
        """,
        items=items,
        total_cents=total_cents,
    )


@app.post("/checkout/create-order")
@login_required
def create_order():
    cart = get_cart()
    if not cart:
        flash('Carrinho vazio', 'warning')
        return redirect(url_for('list_products'))

    order = Order(user_id=current_user.id, status='pending')
    db.session.add(order)
    db.session.flush()

    total_cents = 0
    for product_id_str, quantity in cart.items():
        product = db.session.get(Product, int(product_id_str))
        if not product:
            continue
        q = int(quantity)
        total_cents += product.price_cents * q
        db.session.add(OrderItem(order_id=order.id, product_id=product.id, quantity=q, unit_price_cents=product.price_cents))

    order.total_cents = total_cents
    # Simula pagamento instantâneo
    order.status = 'paid'
    db.session.commit()

    save_cart({})
    flash('Pedido pago (simulado). Agora você pode avaliar o produto.', 'success')
    return redirect(url_for('index'))


@app.post('/reviews/<int:product_id>')
@login_required
def create_review(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        flash('Produto não encontrado', 'warning')
        return redirect(url_for('list_products'))

    try:
        rating = int(request.form.get('rating', ''))
        comment = (request.form.get('comment') or '').strip()
    except Exception:
        flash('Avaliação inválida', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    if rating < 1 or rating > 5 or len(comment) < 10:
        flash('Avaliação inválida', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    if not user_purchased_product(current_user.id, product_id):
        flash('Somente compradores verificados podem avaliar.', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))

    recent = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).limit(10).all()
    for r in recent:
        if is_similar_text(r.comment, comment):
            flash('Avaliação muito similar a outras. Tente ser original.', 'warning')
            return redirect(url_for('product_detail', product_id=product_id))

    review = Review(user_id=current_user.id, product_id=product_id, rating=rating, comment=comment, is_approved=True)
    db.session.add(review)
    db.session.commit()
    flash('Avaliação enviada.', 'success')
    return redirect(url_for('product_detail', product_id=product_id))


@app.get('/search/')
def search():
    q = (request.args.get('q') or '').strip()
    results = []
    if q:
        results = Product.query.filter(
            (Product.name.ilike(f"%{q}%")) | (Product.description.ilike(f"%{q}%"))
        ).all()
    return render_template_string(
        BASE_HTML + """
        {% block content %}
          <h2>Buscar</h2>
          <form method="get">
            <input type="text" name="q" value="{{ q }}">
            <button type="submit">Buscar</button>
          </form>
          <ul>
            {% for p in results %}
              <li><a href="{{ url_for('product_detail', product_id=p.id) }}">{{ p.name }}</a></li>
            {% else %}
              {% if q %}<li>Sem resultados</li>{% endif %}
            {% endfor %}
          </ul>
        {% endblock %}
        """,
        q=q,
        results=results,
    )


# ----------------------------------------------------------------------------
# DB bootstrap
# ----------------------------------------------------------------------------
with app.app_context():
    db.create_all()
    if Product.query.count() == 0:
        db.session.add_all([
            Product(name="Camiseta Python", description="Camiseta confortável com estampa Python.", price_cents=4999),
            Product(name="Caneca Flask", description="Caneca temática do Flask para café.", price_cents=2999),
            Product(name="Adesivo SQLAlchemy", description="Adesivo estiloso para seu laptop.", price_cents=999),
        ])
        # cria um usuário demo
        if not User.query.filter_by(email="demo@example.com").first():
            u = User(email="demo@example.com", name="Demo")
            u.set_password("demo1234")
            db.session.add(u)
        db.session.commit()


# ----------------------------------------------------------------------------
# Entrypoint
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)