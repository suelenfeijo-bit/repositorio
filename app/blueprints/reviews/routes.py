from datetime import datetime, timedelta
from difflib import SequenceMatcher

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.forms import ReviewForm
from app.models import db, Product, Review, Order, OrderItem

reviews_bp = Blueprint("reviews", __name__, template_folder="../../templates/reviews")


def user_purchased_product(user_id: int, product_id: int) -> bool:
    q = (
        db.session.query(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.user_id == user_id, Order.status == 'paid', OrderItem.product_id == product_id)
        .first()
    )
    return q is not None


def is_similar_text(a: str, b: str) -> bool:
    ratio = SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()
    return ratio > 0.9


@reviews_bp.post('/<int:product_id>')
@login_required
def create_review(product_id: int):
    form = ReviewForm()
    product = db.session.get(Product, product_id)
    if not product:
        flash('Product not found', 'warning')
        return redirect(url_for('products.list_products'))

    if not form.validate_on_submit():
        flash('Invalid review', 'danger')
        return redirect(url_for('products.product_detail', product_id=product_id))

    # Anti-fake moderation checks
    if not user_purchased_product(current_user.id, product_id):
        flash('Only verified purchasers can review this product.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    # One review per product per user enforced by DB constraint; also check cooldown of 24h for edits
    existing = Review.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if existing:
        flash('You have already reviewed this product.', 'info')
        return redirect(url_for('products.product_detail', product_id=product_id))

    # Similarity check against recent reviews to prevent copy-paste spam
    recent_reviews = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).limit(10).all()
    for r in recent_reviews:
        if is_similar_text(r.comment, form.comment.data):
            flash('Your review is too similar to existing ones. Please write a unique review.', 'warning')
            return redirect(url_for('products.product_detail', product_id=product_id))

    review = Review(
        user_id=current_user.id,
        product_id=product_id,
        rating=form.rating.data,
        comment=form.comment.data,
        is_moderated=True,
        is_approved=True,
    )
    db.session.add(review)
    db.session.commit()

    flash('Review submitted.', 'success')
    return redirect(url_for('products.product_detail', product_id=product_id))