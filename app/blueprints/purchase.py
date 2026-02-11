from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Vendor, Order, OrderItem, Product, Transaction, GRN, GRNItem, PurchaseInvoice, VendorPayment
from app import db
from app.decorators import role_required
from datetime import datetime

purchase_bp = Blueprint('purchase', __name__)

# --- Vendor Routes ---
@purchase_bp.route('/vendors')
@login_required
@role_required('super_admin', 'admin', 'manager')
def vendors():
    vendors_list = Vendor.query.all()
    from app.ai_engine import AIEngine
    
    # Pre-calculate reliability for each vendor
    for vendor in vendors_list:
        vendor.reliability_score = AIEngine.get_vendor_reliability(vendor.id)
    
    return render_template('purchase/vendors.html', vendors=vendors_list, title='Vendor Management')

@purchase_bp.route('/vendors/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def add_vendor():
    if request.method == 'POST':
        vendor = Vendor(
            name=request.form.get('name'),
            contact_person=request.form.get('contact_person'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            address=request.form.get('address'),
            gstin=request.form.get('gstin')
        )
        try:
            db.session.add(vendor)
            db.session.commit()
            flash('Vendor added successfully!', 'success')
            return redirect(url_for('purchase.vendors'))
        except Exception as e:
            flash(f'Error adding vendor: {str(e)}', 'danger')
    return render_template('purchase/vendor_form.html', title='Add Vendor')

@purchase_bp.route('/vendors/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def edit_vendor(id):
    vendor = Vendor.query.get_or_404(id)
    if request.method == 'POST':
        vendor.name = request.form.get('name')
        vendor.contact_person = request.form.get('contact_person')
        vendor.phone = request.form.get('phone')
        vendor.email = request.form.get('email')
        vendor.address = request.form.get('address')
        vendor.gstin = request.form.get('gstin')
        try:
            db.session.commit()
            flash('Vendor updated successfully!', 'success')
            return redirect(url_for('purchase.vendors'))
        except Exception as e:
            flash(f'Error updating vendor: {str(e)}', 'danger')
    return render_template('purchase/vendor_form.html', vendor=vendor, title='Edit Vendor')

# --- Purchase Order Routes ---
@purchase_bp.route('/purchase/orders')
@login_required
@role_required('super_admin', 'admin', 'manager')
def orders():
    orders = Order.query.filter_by(type='PURCHASE').order_by(Order.date.desc()).all()
    from app.ai_engine import AIEngine
    procurement_insight = AIEngine.get_procurement_insights()
    return render_template('purchase/orders.html', 
                           orders=orders, 
                           procurement_insight=procurement_insight,
                           title='Purchase Orders')

@purchase_bp.route('/purchase/new', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def create_order():
    if request.method == 'POST':
        vendor_id = request.form.get('vendor_id')
        
        # Create Order Header
        order = Order(
            type='PURCHASE',
            vendor_id=vendor_id,
            status='PENDING', # New flow: PO is Pending until Received
            date=datetime.utcnow()
        )
        db.session.add(order)
        db.session.flush()
        
        total_amount = 0
        product_names = request.form.getlist('product_name[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        
        for name, qty, price in zip(product_names, quantities, prices):
            if name and qty and price:
                # Find or Create Product
                product = Product.query.filter_by(name=name.strip()).first()
                if not product:
                    # Generate a simple unique code
                    timestamp = datetime.now().strftime('%y%m%d%H%M%S')
                    new_code = f"AUTO-{timestamp[-6:]}"
                    
                    product = Product(
                        code=new_code,
                        name=name.strip(),
                        category='Raw Material', # Default for new purchases
                        cost_price=float(price),
                        stock_quantity=0,
                        raw_stock=0
                    )
                    db.session.add(product)
                    db.session.flush() # Get the auto-incremented ID

                line_total = float(qty) * float(price)
                item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=float(qty),
                    price=float(price),
                    total=line_total
                )
                db.session.add(item)
                total_amount += line_total

        order.total_amount = total_amount
        order.grand_total = total_amount
        
        try:
            db.session.commit()
            flash('Purchase Order created successfully! Now record the receipt when goods arrive.', 'success')
            return redirect(url_for('purchase.view_order', id=order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating order: {str(e)}', 'danger')

    vendors = Vendor.query.all()
    products = Product.query.all()
    selected_vendor_id = request.args.get('vendor_id', type=int)
    return render_template('purchase/create_order.html', 
                           vendors=vendors, 
                           products=products, 
                           selected_vendor_id=selected_vendor_id,
                           now=datetime.now().strftime('%d %b %Y'),
                           title='New Purchase Order')

@purchase_bp.route('/purchase/view/<int:id>')
@login_required
@role_required('super_admin', 'admin', 'manager', 'store_user') 
def view_order(id):
    order = Order.query.get_or_404(id)
    if order.type != 'PURCHASE':
        flash('Invalid order type.', 'danger')
        return redirect(url_for('purchase.orders'))
    return render_template('purchase/view_order.html', order=order, title=f'Purchase Order #{order.id}')

# --- Goods Receipt (Inward Entry) ---
@purchase_bp.route('/purchase/inward/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager', 'store_user')
def inward_receipt(id):
    order = Order.query.get_or_404(id)
    if request.method == 'POST':
        grn = GRN(
            order_id=order.id,
            grn_number=f"GRN-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            received_by=request.form.get('received_by'),
            remarks=request.form.get('remarks')
        )
        db.session.add(grn)
        db.session.flush()

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity_received[]')
        
        for pid, qty_rec in zip(product_ids, quantities):
            qty_rec = int(qty_rec)
            if qty_rec > 0:
                # Add GRN Item
                grn_item = GRNItem(
                    grn_id=grn.id,
                    product_id=pid,
                    quantity_received=qty_rec
                )
                db.session.add(grn_item)

                # Update Order Item Status
                order_item = OrderItem.query.filter_by(order_id=order.id, product_id=pid).first()
                if order_item:
                    order_item.received_quantity += qty_rec

                # Update Inventory Stock
                product = Product.query.get(pid)
                if product.category == 'Raw Material':
                    product.raw_stock += qty_rec
                    desc = f'Raw Material Inward via GRN {grn.grn_number}'
                else:
                    product.stock_quantity += qty_rec
                    desc = f'Finished Good Inward via GRN {grn.grn_number}'

                # Log Transaction
                txn = Transaction(
                    product_id=pid,
                    type='IN',
                    quantity=qty_rec,
                    reference_model='GRN',
                    reference_id=grn.id,
                    description=desc
                )
                db.session.add(txn)

        order.status = 'RECEIVED'
        try:
            db.session.commit()
            flash(f'Goods Receipt Note {grn.grn_number} created and Stock Updated!', 'success')
            return redirect(url_for('purchase.view_order', id=order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording receipt: {str(e)}', 'danger')

    return render_template('purchase/inward_form.html', order=order, title='Record Goods Receipt')

# --- Vendor Bill / Purchase Invoice ---
@purchase_bp.route('/purchase/bill/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def record_bill(id):
    order = Order.query.get_or_404(id)
    if request.method == 'POST':
        bill = PurchaseInvoice(
            order_id=order.id,
            vendor_id=order.vendor_id,
            invoice_number=request.form.get('invoice_number'),
            invoice_date=datetime.strptime(request.form.get('invoice_date'), '%Y-%m-%d').date(),
            total_amount=request.form.get('total_amount'),
            status='UNPAID'
        )
        order.status = 'BILLED'
        try:
            db.session.add(bill)
            db.session.commit()
            flash('Vendor Bill recorded successfully!', 'success')
            return redirect(url_for('purchase.view_order', id=order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording bill: {str(e)}', 'danger')
            
    return render_template('purchase/bill_form.html', order=order, title='Record Vendor Bill')

# --- Vendor Payment ---
@purchase_bp.route('/purchase/payment/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def record_payment(invoice_id):
    invoice = PurchaseInvoice.query.get_or_404(invoice_id)
    if request.method == 'POST':
        payment = VendorPayment(
            invoice_id=invoice.id,
            amount=request.form.get('amount'),
            payment_mode=request.form.get('payment_mode'),
            transaction_id=request.form.get('transaction_id'),
            remarks=request.form.get('remarks')
        )
        invoice.status = 'PAID' # For simplicity, mark full paid. Partial logic could be added.
        invoice.order.status = 'PAID'
        try:
            db.session.add(payment)
            db.session.commit()
            flash('Payment recorded successfully!', 'success')
            return redirect(url_for('purchase.view_order', id=invoice.order_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording payment: {str(e)}', 'danger')
            
    return render_template('purchase/payment_form.html', invoice=invoice, title='Record Payment')
