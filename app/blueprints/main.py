from flask import Blueprint, render_template, request, flash
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)

from app.models import Setting
from app import db # Need db for saving settings

@main_bp.context_processor
def inject_company_info():
    # Helper to available globally
    def get_setting(key, default=''):
        s = Setting.query.filter_by(key=key).first()
        return s.value if s else default
    return dict(get_setting=get_setting)

@main_bp.route('/')
@login_required
def dashboard():
    from app.models import Product, Order, OrderItem
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Total Products
    total_products = Product.query.count()
    
    # Total Stock Value (Cost Price × Quantity)
    stock_value = db.session.query(
        func.sum(Product.cost_price * Product.stock_quantity)
    ).scalar() or 0
    
    # Low Stock Alerts
    low_stock_count = Product.query.filter(
        Product.stock_quantity <= Product.min_stock_alert
    ).count()
    
    # Today's Sales Activity
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sales_count = Order.query.filter(
        Order.type == 'SALE',
        Order.date >= today_start
    ).count()

    # Monthly Revenue
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = db.session.query(
        func.sum(Order.total_amount)
    ).filter(
        Order.type == 'SALE',
        Order.date >= month_start
    ).scalar() or 0
    
    # Category-wise Stock Distribution
    category_stock = db.session.query(
        Product.category,
        func.sum(Product.stock_quantity).label('total_stock')
    ).group_by(Product.category).all()
    
    category_names = [c[0] or 'Uncategorized' for c in category_stock]
    category_quantities = [int(c[1]) for c in category_stock]
    
    # Low Stock Products
    low_stock_products = Product.query.filter(
        Product.stock_quantity <= Product.min_stock_alert
    ).limit(5).all()
    
    # Send Email if low stock detected and not sent today
    if low_stock_count > 0:
        try:
            from app.email_service import EmailService
            all_low_stock = Product.query.filter(
                Product.stock_quantity <= Product.min_stock_alert
            ).all()
            # Only send email once per day per product - you could add more complex logic here
            EmailService.send_low_stock_alert(all_low_stock)
        except Exception as e:
            print(f"Low stock email failed: {e}")
    
    # Prepare data for category legend
    category_data = zip(category_names, category_quantities)
    category_colors = ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#5a5c69']
    
    # Initialize company name if it doesn't exist
    company_setting = Setting.query.filter_by(key='company_name').first()
    if not company_setting or company_setting.value == '':
        if not company_setting:
            db.session.add(Setting(key='company_name', value='Gharana Gold'))
        else:
            company_setting.value = 'Gharana Gold'
        db.session.commit()

    # AI Engine Insights
    from app.ai_engine import AIEngine
    ai_insights = AIEngine.get_stock_insights()
    ai_forecast = AIEngine.get_forecasting_data()

    return render_template('dashboard/index.html', 
                         title='Gharana Gold | AI Dashboard',
                         total_products=total_products,
                         stock_value=round(stock_value, 2),
                         low_stock_count=low_stock_count,
                         today_sales_count=today_sales_count,
                         monthly_revenue=round(monthly_revenue, 2),
                         category_names=category_names,
                         category_quantities=category_quantities,
                         category_data=category_data,
                         colors=category_colors,
                         low_stock_products=low_stock_products,
                         ai_insights=ai_insights,
                         ai_forecast=ai_forecast)



