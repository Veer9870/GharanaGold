from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Product, Order, OrderItem, Customer, Transaction
from app import db
from app.decorators import role_required
from datetime import datetime
from sqlalchemy import func

sales_bp = Blueprint('sales', __name__)

@sales_bp.route('/sales')
@login_required
@role_required('super_admin', 'admin', 'manager')
def index():
    # Fetch all sales (outward items)
    sales = Order.query.filter_by(type='SALE').order_by(Order.date.desc()).all()
    
    # Calculate daily sales for graph
    daily_sales = db.session.query(
        func.date(Order.date).label('date'),
        func.sum(Order.total_amount).label('total')
    ).filter(Order.type == 'SALE').group_by(func.date(Order.date)).order_by('date').all()
    
    chart_labels = [str(d.date) for d in daily_sales]
    chart_data = [float(d.total) for d in daily_sales]
    
    return render_template('sales/index.html', 
                         sales=sales, 
                         chart_labels=chart_labels, 
                         chart_data=chart_data,
                         title='Sales & Dispatches')

@sales_bp.route('/sales/create', methods=['GET', 'POST'])
@login_required
def create_sale():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        
        if not product_ids:
            flash('Please add at least one item.', 'danger')
            return redirect(url_for('sales.create_sale'))
            
        try:
            new_sale = Order(
                type='SALE',
                customer_id=customer_id if customer_id else None,
                status='COMPLETED', # For now, outward entry is immediate completion
                total_amount=0
            )
            db.session.add(new_sale)
            db.session.flush() # Get sale ID
            
            total_amount = 0
            for pid, qty, prc in zip(product_ids, quantities, prices):
                qty = int(qty)
                prc = float(prc)
                line_total = qty * prc
                
                # Check stock
                product = Product.query.get(pid)
                if product.stock_quantity < qty:
                    db.session.rollback()
                    flash(f'Insufficient stock for {product.name}. Available: {product.stock_quantity}', 'danger')
                    return redirect(url_for('sales.create_sale'))
                
                item = OrderItem(
                    order_id=new_sale.id,
                    product_id=pid,
                    quantity=qty,
                    price=prc,
                    total=line_total
                )
                db.session.add(item)
                
                # Update Stock
                product.stock_quantity -= qty
                
                # Log Transaction
                txn = Transaction(
                    product_id=pid,
                    type='OUT',
                    quantity=qty,
                    reference_model='Order',
                    reference_id=new_sale.id,
                    description=f"Sales Outward #SALE-{new_sale.id}"
                )
                db.session.add(txn)
                
                total_amount += line_total
            
            new_sale.total_amount = total_amount
            new_sale.grand_total = total_amount
            db.session.commit()
            
            flash('Sales entry recorded and inventory adjusted.', 'success')
            return redirect(url_for('sales.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating sale: {str(e)}', 'danger')
            
    products = Product.query.filter(Product.stock_quantity > 0).all()
    customers = Customer.query.all()
    return render_template('sales/create.html', products=products, customers=customers)

@sales_bp.route('/sales/customers')
@login_required
def customers():
    customers_list = Customer.query.all()
    return render_template('sales/customers.html', customers=customers_list)

@sales_bp.route('/sales/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        customer = Customer(
            name=request.form.get('name'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            address=request.form.get('address'),
            gstin=request.form.get('gstin')
        )
        db.session.add(customer)
        db.session.commit()
        flash('Customer registered successfully!', 'success')
        return redirect(url_for('sales.customers'))
    return render_template('sales/add_customer.html')

@sales_bp.route('/sales/customers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    
    if request.method == 'POST':
        customer.name = request.form.get('name')
        customer.phone = request.form.get('phone')
        customer.email = request.form.get('email')
        customer.address = request.form.get('address')
        customer.gstin = request.form.get('gstin')
        
        try:
            db.session.commit()
            flash('Customer updated successfully!', 'success')
            return redirect(url_for('sales.customers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating customer: {str(e)}', 'danger')
    
    return render_template('sales/edit_customer.html', customer=customer)

@sales_bp.route('/sales/customers/delete/<int:id>')
@login_required
@role_required('super_admin', 'admin')
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    
    # Check if customer has any orders
    if customer.orders:
        flash('Cannot delete customer with existing orders.', 'danger')
        return redirect(url_for('sales.customers'))
    
    try:
        db.session.delete(customer)
        db.session.commit()
        flash('Customer deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting customer: {str(e)}', 'danger')
    
    return redirect(url_for('sales.customers'))

@sales_bp.route('/sales/receipt/<int:id>')
@login_required
def receipt(id):
    order = Order.query.get_or_404(id)
    return render_template('sales/receipt.html', order=order)
