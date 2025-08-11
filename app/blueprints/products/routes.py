from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.forms import ProductForm
from app.models import db, Product

products_bp = Blueprint("products", __name__, template_folder="../../templates/products")


@products_bp.get("/")
def list_products():
    page = max(int(request.args.get('page', 1)), 1)
    per_page = 12
    pagination = Product.query.filter_by(active=True).order_by(Product.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template("products/list.html", pagination=pagination, products=pagination.items)


@products_bp.get("/<int:product_id>")
def product_detail(product_id: int):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        flash("Product not found", "warning")
        return redirect(url_for("products.list_products"))
    return render_template("products/detail.html", product=product)


@products_bp.get("/new")
@login_required
def new_product():
    form = ProductForm()
    return render_template("products/new.html", form=form)


@products_bp.post("/new")
@login_required
def create_product():
    form = ProductForm()
    if not form.validate_on_submit():
        flash("Invalid data", "danger")
        return redirect(url_for("products.new_product"))

    product = Product(
        name=form.name.data,
        description=form.description.data,
        price_cents=form.price_cents.data,
    )
    db.session.add(product)
    db.session.commit()
    flash("Product created", "success")
    return redirect(url_for("products.product_detail", product_id=product.id))