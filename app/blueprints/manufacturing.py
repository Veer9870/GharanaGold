from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app.models import Product, Transaction
from app import db
from datetime import datetime, timedelta
from app.decorators import role_required
from sqlalchemy import func

manufacturing_bp = Blueprint('manufacturing', __name__)

@manufacturing_bp.route('/manufacturing')
@login_required
def index():
    # Fetch all production logs
    logs = Transaction.query.filter_by(type='PRODUCTION').order_by(Transaction.date.desc()).limit(100).all()
    
    today = datetime.utcnow().date()
    today_count = 0
    today_items = {} 
    
    # 1. Today's Breakdown
    for log in logs:
        if log.date.date() == today:
            today_count += log.quantity
            if log.product.name in today_items:
                today_items[log.product.name] += log.quantity
            else:
                today_items[log.product.name] = log.quantity

    # 2. Weekly Trend (Last 7 Days)
    weekly_labels = []
    weekly_values = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        weekly_labels.append(day.strftime('%d %b'))
        # Sum quantity for this specific day
        daily_sum = db.session.query(func.sum(Transaction.quantity)).filter(
            Transaction.type == 'PRODUCTION',
            func.date(Transaction.date) == day
        ).scalar() or 0
        weekly_values.append(int(daily_sum))

    # 3. Monthly Trend (Current Month)
    first_of_month = today.replace(day=1)
    monthly_sum = db.session.query(func.sum(Transaction.quantity)).filter(
        Transaction.type == 'PRODUCTION',
        Transaction.date >= first_of_month
    ).scalar() or 0

    return render_template('manufacturing/index.html', 
                         logs=logs, 
                         today_count=today_count, 
                         today_items=today_items,
                         weekly_labels=weekly_labels,
                         weekly_values=weekly_values,
                         monthly_total=int(monthly_sum))

@manufacturing_bp.route('/manufacturing/export')
@login_required
@role_required('super_admin', 'admin', 'manager')
def export_csv():
    import csv
    import io
    from flask import Response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Date', 'Product name', 'Quantity', 'Unit', 'Batch Number', 'Notes'])
    
    # Data
    logs = Transaction.query.filter_by(type='PRODUCTION').order_by(Transaction.date.desc()).all()
    for log in logs:
        writer.writerow([
            log.date.strftime('%Y-%m-%d %H:%M'),
            log.product.name,
            log.quantity,
            log.product.unit,
            log.product.batch_number,
            log.description
        ])
    
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=manufacturing_report_{datetime.now().strftime('%Y%p%d')}.csv"}
    )

@manufacturing_bp.route('/manufacturing/new', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin', 'manager')
def new():
    if request.method == 'POST':
        try:
            product_name = request.form.get('product_name')
            quantity = int(request.form.get('quantity'))
            batch_no = request.form.get('batch_number')
            expiry = request.form.get('expiry_date')
            notes = request.form.get('notes')
            
            product = Product.query.filter_by(name=product_name).first()
            if not product:
                flash(f'Product "{product_name}" not found. Please select an existing SKU.', 'danger')
                return redirect(url_for('manufacturing.new'))
            
            # Increase Stock
            product.stock_quantity += quantity
            
            # Update Batch Info (Optional: this overwrites current batch of product. 
            # In simple ERPs this is often acceptable behavior for "Current Batch")
            if batch_no:
                product.batch_number = batch_no
            if expiry:
                product.expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
            
            # Log Transaction
            txn = Transaction(
                product_id=product.id,
                type='PRODUCTION',
                quantity=quantity,
                date=datetime.utcnow(),
                description=f'Batch: {batch_no} | {notes}' if batch_no else notes or 'Production Run',
                reference_model='Production',
                reference_id=0
            )
            
            db.session.add(txn)
            db.session.commit()
            flash(f'Successfully recorded production of {quantity} {product.unit} {product.name}', 'success')
            return redirect(url_for('manufacturing.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording production: {str(e)}', 'danger')
            
    products = Product.query.filter_by().all()
    return render_template('manufacturing/form.html', products=products)
