from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response
from flask_login import login_required, current_user
from app.models import Product, Transaction, Vendor
from app import db
from app.decorators import role_required
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import os
import secrets
from flask import current_app
import io
import csv


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, 'static/images/products', picture_fn)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)
    
    form_picture.save(picture_path)
    return picture_fn

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory')
@login_required
@role_required('super_admin', 'admin', 'manager', 'store_user')
def index():
    # Get filter parameters
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    stock_filter = request.args.get('stock_filter', '')
    
    # Base query
    query = Product.query
    
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search}%'),
                Product.code.ilike(f'%{search}%'),
                Product.brand.ilike(f'%{search}%')
            )
        )
    
    # Apply category filter
    if category:
        query = query.filter(Product.category == category)
    
    # Apply stock filter
    if stock_filter == 'low':
        query = query.filter(Product.stock_quantity <= Product.min_stock_alert)
    elif stock_filter == 'out':
        query = query.filter(Product.stock_quantity == 0)
    elif stock_filter == 'healthy':
        query = query.filter(Product.stock_quantity > Product.min_stock_alert)
    
    products = query.order_by(Product.name).all()
    
    # Get unique categories for filter dropdown
    categories = db.session.query(Product.category).distinct().filter(Product.category.isnot(None)).all()
    categories = [c[0] for c in categories if c[0]]
    
    # Calculate inventory statistics
    total_products = Product.query.count()
    # Total Value = Stock Value (Saleable) + Raw Stock Value (Raw Materials)
    total_value = db.session.query(func.sum(Product.stock_quantity * Product.cost_price)).scalar() or 0
    total_raw_value = db.session.query(func.sum(Product.raw_stock * Product.cost_price)).scalar() or 0
    
    low_stock_count = Product.query.filter(Product.stock_quantity <= Product.min_stock_alert).count()
    out_of_stock = Product.query.filter(Product.stock_quantity == 0, Product.category != 'Raw Material').count()
    raw_material_count = Product.query.filter(Product.category == 'Raw Material').count()
    
    # Get expiring soon products (next 30 days)
    expiry_date_threshold = datetime.now().date() + timedelta(days=30)
    expiring_soon = Product.query.filter(
        Product.expiry_date.isnot(None),
        Product.expiry_date <= expiry_date_threshold,
        (Product.stock_quantity > 0) | (Product.raw_stock > 0)
    ).count()
    
    stats = {
        'total_products': total_products,
        'total_value': float(total_value) + float(total_raw_value),
        'saleable_value': float(total_value),
        'raw_value': float(total_raw_value),
        'low_stock': low_stock_count,
        'out_of_stock': out_of_stock,
        'expiring_soon': expiring_soon,
        'raw_materials': raw_material_count
    }
    
    return render_template('inventory/index.html', 
                          products=products, 
                          categories=categories,
                          stats=stats,
                          search=search,
                          selected_category=category,
                          stock_filter=stock_filter,
                          today=datetime.now().date(),
                          title='Inventory Management')

@inventory_bp.route('/inventory/dashboard')
@login_required
@role_required('super_admin', 'admin', 'manager')
def dashboard():
    """Advanced inventory analytics dashboard"""
    
    # Total inventory value
    total_value = db.session.query(func.sum(Product.stock_quantity * Product.cost_price)).scalar() or 0
    potential_revenue = db.session.query(func.sum(Product.stock_quantity * Product.selling_price)).scalar() or 0
    
    # Category breakdown
    category_data = db.session.query(
        Product.category,
        func.count(Product.id).label('count'),
        func.sum(Product.stock_quantity).label('total_stock'),
        func.sum(Product.stock_quantity * Product.cost_price).label('value')
    ).group_by(Product.category).all()
    
    # Stock movement (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    stock_in = db.session.query(func.sum(Transaction.quantity)).filter(
        Transaction.type == 'IN',
        Transaction.date >= thirty_days_ago
    ).scalar() or 0
    
    stock_out = db.session.query(func.sum(Transaction.quantity)).filter(
        Transaction.type == 'OUT',
        Transaction.date >= thirty_days_ago
    ).scalar() or 0
    
    # Daily movement for chart
    daily_movement = db.session.query(
        func.date(Transaction.date).label('date'),
        Transaction.type,
        func.sum(Transaction.quantity).label('quantity')
    ).filter(Transaction.date >= thirty_days_ago).group_by(
        func.date(Transaction.date), Transaction.type
    ).all()
    
    # Low stock products
    low_stock_products = Product.query.filter(
        Product.stock_quantity <= Product.min_stock_alert,
        Product.stock_quantity > 0
    ).order_by(Product.stock_quantity).limit(10).all()
    
    # Out of stock products
    out_of_stock_products = Product.query.filter(Product.stock_quantity == 0).all()
    
    # Expiring products
    expiry_threshold = datetime.now().date() + timedelta(days=30)
    expiring_products = Product.query.filter(
        Product.expiry_date.isnot(None),
        Product.expiry_date <= expiry_threshold,
        Product.stock_quantity > 0
    ).order_by(Product.expiry_date).all()
    
    # Top moving products
    top_products = db.session.query(
        Product,
        func.sum(Transaction.quantity).label('total_movement')
    ).join(Transaction).filter(
        Transaction.date >= thirty_days_ago
    ).group_by(Product.id).order_by(desc('total_movement')).limit(5).all()
    
    # Prepare chart data
    # Prepare chart data
    chart_dates = [(thirty_days_ago + timedelta(days=x)).strftime('%Y-%m-%d') for x in range(31)]
    
    # Initialize data maps
    data_in_map = {date: 0 for date in chart_dates}
    data_out_map = {date: 0 for date in chart_dates}
    
    for item in daily_movement:
        # Ensure date is string formatted correctly
        date_val = item.date
        if hasattr(date_val, 'strftime'):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val)
            
        if date_str in data_in_map:
            if item.type == 'IN':
                data_in_map[date_str] += int(item.quantity) # Use += to be safe
            else:
                data_out_map[date_str] += int(item.quantity)
    
    # Convert to aligned lists
    chart_in_data = [data_in_map[date] for date in chart_dates]
    chart_out_data = [data_out_map[date] for date in chart_dates]
    
    return render_template('inventory/dashboard.html',
                          total_value=float(total_value),
                          potential_revenue=float(potential_revenue),
                          stock_in=stock_in,
                          stock_out=stock_out,
                          category_data=category_data,
                          low_stock_products=low_stock_products,
                          out_of_stock_products=out_of_stock_products,
                          expiring_products=expiring_products,
                          top_products=top_products,
                          chart_labels=chart_dates,
                          chart_in=chart_in_data,
                          chart_out=chart_out_data,
                          title='Inventory Analytics')

@inventory_bp.route('/inventory/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def add_product():
    if request.method == 'POST':
        code = request.form.get('code')
        if Product.query.filter_by(code=code).first():
            flash(f'Error: Product code {code} already exists!', 'danger')
            return render_template('inventory/form.html', title='Add Product')

        # Parse expiry date
        expiry_date = None
        expiry_str = request.form.get('expiry_date')
        if expiry_str:
            try:
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        category = request.form.get('category')
        initial_qty = int(request.form.get('stock_quantity', 0))
        
        product = Product(
            code=code,
            name=request.form.get('name'),
            category=category,
            brand=request.form.get('brand'),
            unit=request.form.get('unit'),
            cost_price=request.form.get('cost_price'),
            selling_price=request.form.get('selling_price'),
            gst_percent=request.form.get('gst_percent'),
            stock_quantity=initial_qty if category != 'Raw Material' else 0,
            raw_stock=initial_qty if category == 'Raw Material' else 0,
            min_stock_alert=request.form.get('min_stock_alert', 10),
            warehouse_location=request.form.get('warehouse_location'),
            batch_number=request.form.get('batch_number'),
            expiry_date=expiry_date,
            vendor_id=request.form.get('vendor_id') or None
        )
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                image_file = save_picture(file)
                product.image_file = image_file
        
        try:
            db.session.add(product)
            db.session.flush()
            
            # Create initial stock transaction
            initial_stock = int(request.form.get('stock_quantity', 0))
            if initial_stock > 0:
                txn = Transaction(
                    product_id=product.id,
                    type='IN',
                    quantity=initial_stock,
                    reference_model='Initial',
                    description='Initial stock entry on product creation'
                )
                db.session.add(txn)
            
            db.session.commit()
            flash('Product added successfully!', 'success')
            return redirect(url_for('inventory.index'))
        except Exception as e:
            db.session.rollback()
            if 'UNIQUE constraint failed' in str(e):
                flash(f'Error: Product code {code} must be unique.', 'danger')
            else:
                flash(f'Error adding product: {str(e)}', 'danger')

    vendors = Vendor.query.order_by(Vendor.name).all()
    return render_template('inventory/form.html', title='Add Product', vendors=vendors)

@inventory_bp.route('/inventory/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def edit_product(id):
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        product.code = request.form.get('code')
        product.name = request.form.get('name')
        product.category = request.form.get('category')
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                image_file = save_picture(file)
                product.image_file = image_file
        product.brand = request.form.get('brand')
        product.unit = request.form.get('unit')
        product.cost_price = request.form.get('cost_price')
        product.selling_price = request.form.get('selling_price')
        product.gst_percent = request.form.get('gst_percent')
        product.min_stock_alert = request.form.get('min_stock_alert')
        product.warehouse_location = request.form.get('warehouse_location')
        product.batch_number = request.form.get('batch_number')
        
        # Parse expiry date
        expiry_str = request.form.get('expiry_date')
        if expiry_str:
            try:
                product.expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            product.expiry_date = None
        
        product.vendor_id = request.form.get('vendor_id') or None
        
        try:
            db.session.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('inventory.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'danger')

    vendors = Vendor.query.order_by(Vendor.name).all()
    return render_template('inventory/form.html', product=product, title='Edit Product', vendors=vendors)

@inventory_bp.route('/inventory/view/<int:id>')
@login_required
@role_required('super_admin', 'admin', 'manager', 'store_user')
def view_product(id):
    """View detailed product information with transaction history"""
    product = Product.query.get_or_404(id)
    
    # Get transaction history
    transactions = Transaction.query.filter_by(product_id=id).order_by(desc(Transaction.date)).limit(50).all()
    
    # Calculate stats
    total_in = db.session.query(func.sum(Transaction.quantity)).filter(
        Transaction.product_id == id, 
        Transaction.type == 'IN'
    ).scalar() or 0
    
    total_out = db.session.query(func.sum(Transaction.quantity)).filter(
        Transaction.product_id == id, 
        Transaction.type == 'OUT'
    ).scalar() or 0
    
    return render_template('inventory/view.html', 
                          product=product, 
                          transactions=transactions,
                          total_in=total_in,
                          total_out=total_out,
                          today=datetime.now().date(),
                          title=f'Product: {product.name}')

@inventory_bp.route('/inventory/delete/<int:id>')
@login_required
@role_required('super_admin', 'admin')
def delete_product(id):
    product = Product.query.get_or_404(id)
    try:
        # Delete related transactions first
        Transaction.query.filter_by(product_id=id).delete()
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Cannot delete product. It might be linked to existing orders.', 'danger')
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/inventory/adjust/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def adjust_stock(id):
    """Manual stock adjustment with reason tracking"""
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        adjustment_type = request.form.get('adjustment_type')  # 'add' or 'remove'
        quantity = int(request.form.get('quantity', 0))
        reason = request.form.get('reason', '')
        
        if quantity <= 0:
            flash('Quantity must be greater than 0', 'danger')
            return redirect(url_for('inventory.adjust_stock', id=id))
        
        if adjustment_type == 'remove' and quantity > product.stock_quantity:
            flash(f'Cannot remove {quantity} units. Only {product.stock_quantity} available.', 'danger')
            return redirect(url_for('inventory.adjust_stock', id=id))
        
        try:
            if adjustment_type == 'add':
                product.stock_quantity += quantity
                txn_type = 'IN'
                description = f'Stock Adjustment (Add): {reason}' if reason else 'Manual stock addition'
            else:
                product.stock_quantity -= quantity
                txn_type = 'OUT'
                description = f'Stock Adjustment (Remove): {reason}' if reason else 'Manual stock removal'
            
            # Log transaction
            txn = Transaction(
                product_id=id,
                type=txn_type,
                quantity=quantity,
                reference_model='Adjustment',
                description=description
            )
            db.session.add(txn)
            db.session.commit()
            
            flash(f'Stock adjusted successfully! New quantity: {product.stock_quantity}', 'success')
            return redirect(url_for('inventory.view_product', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adjusting stock: {str(e)}', 'danger')
    
    return render_template('inventory/adjust.html', product=product, title='Adjust Stock')

@inventory_bp.route('/inventory/quick-update', methods=['POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def quick_update():
    """Quick inline stock update from inventory list"""
    product_id = request.form.get('product_id')
    new_quantity = request.form.get('quantity')
    
    try:
        product = Product.query.get_or_404(product_id)
        is_raw = product.category == 'Raw Material'
        old_quantity = product.raw_stock if is_raw else product.stock_quantity
        new_quantity = int(new_quantity)
        
        if new_quantity < 0:
            return jsonify({'success': False, 'message': 'Quantity cannot be negative'})
        
        difference = new_quantity - old_quantity
        if is_raw:
            product.raw_stock = new_quantity
        else:
            product.stock_quantity = new_quantity
        
        # Log the adjustment
        if difference != 0:
            txn = Transaction(
                product_id=product_id,
                type='IN' if difference > 0 else 'OUT',
                quantity=abs(difference),
                reference_model='QuickUpdate',
                description=f'Quick update: {old_quantity} → {new_quantity}'
            )
            db.session.add(txn)
        
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': f'Stock updated to {new_quantity}',
            'new_quantity': new_quantity
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@inventory_bp.route('/inventory/history')
@login_required
@role_required('super_admin', 'admin', 'manager')
def stock_history():
    """View all stock movement history"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filters
    product_id = request.args.get('product_id', type=int)
    txn_type = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = Transaction.query
    
    if product_id:
        query = query.filter(Transaction.product_id == product_id)
    if txn_type:
        query = query.filter(Transaction.type == txn_type)
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Transaction.date >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Transaction.date < to_date)
        except ValueError:
            pass
    
    transactions = query.order_by(desc(Transaction.date)).paginate(page=page, per_page=per_page)
    products = Product.query.order_by(Product.name).all()
    
    return render_template('inventory/history.html', 
                          transactions=transactions, 
                          products=products,
                          selected_product=product_id,
                          selected_type=txn_type,
                          date_from=date_from,
                          date_to=date_to,
                          title='Stock Movement History')

@inventory_bp.route('/inventory/history/export')
@login_required
@role_required('super_admin', 'admin', 'manager')
def export_stock_history():
    """Export filtered stock movement history to CSV"""
    product_id = request.args.get('product_id', type=int)
    txn_type = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = Transaction.query
    
    if product_id:
        query = query.filter(Transaction.product_id == product_id)
    if txn_type:
        query = query.filter(Transaction.type == txn_type)
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Transaction.date >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Transaction.date < to_date)
        except ValueError:
            pass
            
    transactions = query.order_by(desc(Transaction.date)).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Date', 'Time', 'Product SKU', 'Product Name', 'Type', 'Quantity', 'Unit', 'Reference', 'Description'])
    
    for txn in transactions:
        writer.writerow([
            txn.date.strftime('%Y-%m-%d'),
            txn.date.strftime('%H:%M:%S'),
            txn.product.code,
            txn.product.name,
            'IN' if txn.type == 'IN' else 'OUT',
            txn.quantity,
            txn.product.unit,
            f"{txn.reference_model or 'Manual'} #{txn.reference_id or ''}",
            txn.description or ''
        ])
    
    output.seek(0)
    
    filename = f"stock_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )


@inventory_bp.route('/inventory/alerts')
@login_required
@role_required('super_admin', 'admin', 'manager')
def alerts():
    """View all inventory alerts in one place"""
    
    # Low stock products
    low_stock = Product.query.filter(
        Product.stock_quantity <= Product.min_stock_alert,
        Product.stock_quantity > 0
    ).order_by(Product.stock_quantity).all()
    
    # Out of stock products
    out_of_stock = Product.query.filter(Product.stock_quantity == 0).all()
    
    # Expiring products (next 30 days)
    expiry_threshold = datetime.now().date() + timedelta(days=30)
    expiring = Product.query.filter(
        Product.expiry_date.isnot(None),
        Product.expiry_date <= expiry_threshold,
        Product.stock_quantity > 0
    ).order_by(Product.expiry_date).all()
    
    # Already expired
    expired = Product.query.filter(
        Product.expiry_date.isnot(None),
        Product.expiry_date < datetime.now().date(),
        Product.stock_quantity > 0
    ).all()
    
    return render_template('inventory/alerts.html',
                          low_stock=low_stock,
                          out_of_stock=out_of_stock,
                          expiring=expiring,
                          expired=expired,
                          today=datetime.now().date(),
                          title='Inventory Alerts')

@inventory_bp.route('/api/products/search')
@login_required
def api_search_products():
    """API endpoint for product search (for autocomplete etc.)"""
    query = request.args.get('q', '')
    products = Product.query.filter(
        db.or_(
            Product.name.ilike(f'%{query}%'),
            Product.code.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': p.id,
        'code': p.code,
        'name': p.name,
        'stock': p.stock_quantity,
        'price': float(p.selling_price or 0)
    } for p in products])

@inventory_bp.route('/api/vendor-products/<int:vendor_id>')
@login_required
def api_vendor_products(vendor_id):
    """Fetch products associated with a specific vendor"""
    products = Product.query.filter_by(vendor_id=vendor_id).all()
    return jsonify([{
        'id': p.id,
        'code': p.code,
        'name': p.name,
        'cost_price': float(p.cost_price or 0),
        'unit': p.unit
    } for p in products])
