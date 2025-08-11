import stripe
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user

from app.models import db, Product, Order, OrderItem, Payment
from app import csrf

checkout_bp = Blueprint("checkout", __name__, template_folder="../../templates/checkout")


def get_cart():
    return session.setdefault('cart', {})


def save_cart(cart):
    session['cart'] = cart
    session.modified = True


@checkout_bp.post('/cart/add/<int:product_id>')
def add_to_cart(product_id: int):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        flash('Product not found', 'warning')
        return redirect(url_for('products.list_products'))
    cart = get_cart()
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    save_cart(cart)
    flash('Added to cart', 'success')
    return redirect(url_for('products.product_detail', product_id=product_id))


@checkout_bp.get('/cart')
def view_cart():
    cart = get_cart()
    product_ids = [int(pid) for pid in cart.keys()]
    products = Product.query.filter(Product.id.in_(product_ids)).all() if product_ids else []
    items = []
    total_cents = 0
    for product in products:
        quantity = cart.get(str(product.id), 0)
        line_total = product.price_cents * quantity
        total_cents += line_total
        items.append({
            'product': product,
            'quantity': quantity,
            'line_total': line_total,
        })
    return render_template('checkout/cart.html', items=items, total_cents=total_cents)


@checkout_bp.post('/create-order')
@login_required
def create_order():
    cart = get_cart()
    if not cart:
        flash('Cart is empty', 'warning')
        return redirect(url_for('products.list_products'))

    order = Order(user_id=current_user.id, status='pending')
    db.session.add(order)
    db.session.flush()

    total_cents = 0
    for product_id_str, quantity in cart.items():
        product = db.session.get(Product, int(product_id_str))
        if not product:
            continue
        item = OrderItem(order_id=order.id, product_id=product.id, quantity=int(quantity), unit_price_cents=product.price_cents)
        db.session.add(item)
        total_cents += product.price_cents * int(quantity)

    order.total_cents = total_cents
    db.session.commit()

    # Clear cart
    save_cart({})

    return redirect(url_for('checkout.start_checkout', order_id=order.id))


@checkout_bp.get('/start/<int:order_id>')
@login_required
def start_checkout(order_id: int):
    order = db.session.get(Order, order_id)
    if not order or order.user_id != current_user.id or order.status != 'pending':
        flash('Order not available', 'danger')
        return redirect(url_for('products.list_products'))

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    line_items = []
    for item in order.items:
        product = item.product
        line_items.append({
            'price_data': {
                'currency': order.currency,
                'product_data': {
                    'name': product.name,
                    'description': product.description[:200]
                },
                'unit_amount': item.unit_price_cents
            },
            'quantity': item.quantity
        })

    session_obj = stripe.checkout.Session.create(
        payment_method_types=['card'],
        mode='payment',
        line_items=line_items,
        success_url=url_for('checkout.success', order_id=order.id, _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('checkout.cancel', order_id=order.id, _external=True)
    )

    order.stripe_session_id = session_obj['id']
    db.session.commit()

    return render_template('checkout/redirect.html', checkout_session_id=session_obj['id'], stripe_public_key=current_app.config['STRIPE_PUBLISHABLE_KEY'])


@checkout_bp.get('/success/<int:order_id>')
@login_required
def success(order_id: int):
    order = db.session.get(Order, order_id)
    if not order or order.user_id != current_user.id:
        flash('Order not found', 'warning')
        return redirect(url_for('products.list_products'))
    flash('If payment succeeded, your order will be marked as paid shortly.', 'info')
    return render_template('checkout/success.html', order=order)


@checkout_bp.get('/cancel/<int:order_id>')
@login_required
def cancel(order_id: int):
    flash('Checkout canceled', 'warning')
    return redirect(url_for('products.list_products'))


@checkout_bp.post('/webhooks/stripe')
@csrf.exempt
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = current_app.config['STRIPE_WEBHOOK_SECRET']
    event = None
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        return {}, 400

    if event['type'] == 'checkout.session.completed':
        session_obj = event['data']['object']
        session_id = session_obj.get('id')
        order = Order.query.filter_by(stripe_session_id=session_id).first()
        if order and order.status != 'paid':
            order.status = 'paid'
            payment = Payment(
                order_id=order.id,
                provider='stripe',
                provider_payment_id=session_id,
                amount_cents=order.total_cents,
                currency=order.currency,
                status='succeeded'
            )
            db.session.add(payment)
            db.session.commit()
    return jsonify(success=True)