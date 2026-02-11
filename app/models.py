from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

# --- Settings Model ---
class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)

    @staticmethod
    def get(key, default=None):
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            # Handle boolean strings
            if setting.value == 'True': return True
            if setting.value == 'False': return False
            return setting.value
        return default

# --- Authentication Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    # Role: 'super_admin', 'admin', 'manager', 'store_user'
    role = db.Column(db.String(20), nullable=False, default='store_user')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_role(self, *roles):
        return self.role in roles

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


# --- Inventory Models ---
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False) # Auto-generated or manual
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    brand = db.Column(db.String(50))
    unit = db.Column(db.String(20)) # Kg, Packet, Box
    cost_price = db.Column(db.Numeric(10, 2))
    selling_price = db.Column(db.Numeric(10, 2))
    gst_percent = db.Column(db.Numeric(5, 2), default=0.0)
    stock_quantity = db.Column(db.Integer, default=0) # Saleable / Finished Goods
    raw_stock = db.Column(db.Integer, default=0)      # Used for Production
    min_stock_alert = db.Column(db.Integer, default=10)
    batch_number = db.Column(db.String(50))
    expiry_date = db.Column(db.Date)
    warehouse_location = db.Column(db.String(100))
    image_file = db.Column(db.String(100), default='default.jpg')
    
    # Primary Vendor association
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    vendor = db.relationship('Vendor', backref='products', lazy=True)

class Transaction(db.Model):
    """Tracks stock history"""
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False) # 'IN', 'OUT'
    quantity = db.Column(db.Integer, nullable=False)
    reference_model = db.Column(db.String(50)) # 'Order', 'Adjustment'
    reference_id = db.Column(db.Integer)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200))


# --- Purchase Models ---
class Vendor(db.Model):
    __tablename__ = 'vendors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(20))
    
    orders = db.relationship('Order', backref='vendor', lazy=True, foreign_keys='Order.vendor_id')

# --- Sales Models ---
class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(20))
    
    orders = db.relationship('Order', backref='customer', lazy=True, foreign_keys='Order.customer_id')

# --- Common Order Models (Purchase & Sales) ---
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False) # 'PURCHASE', 'SALE'
    
    # Foreign Keys
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    
    date = db.Column(db.DateTime, default=datetime.utcnow)
    # Status: 'PENDING', 'RECEIVED', 'BILLED', 'PAID', 'CANCELLED'
    status = db.Column(db.String(20), default='PENDING') 
    total_amount = db.Column(db.Numeric(12, 2), default=0.0)
    discount = db.Column(db.Numeric(12, 2), default=0.0)
    tax_amount = db.Column(db.Numeric(12, 2), default=0.0)
    grand_total = db.Column(db.Numeric(12, 2), default=0.0)
    
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")
    grns = db.relationship('GRN', backref='order', lazy=True)
    invoices = db.relationship('PurchaseInvoice', backref='order', lazy=True)

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    quantity = db.Column(db.Integer, nullable=False)
    received_quantity = db.Column(db.Integer, default=0)
    price = db.Column(db.Numeric(10, 2), nullable=False) # Cost Price for Purchase, Selling Price for Sales
    tax_amount = db.Column(db.Numeric(10, 2), default=0.0)
    total = db.Column(db.Numeric(10, 2), nullable=False)

# --- Purchase Flow Specific Models ---

class GRN(db.Model):
    """Goods Receipt Note (Inward Entry)"""
    __tablename__ = 'grns'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    grn_number = db.Column(db.String(20), unique=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    received_by = db.Column(db.String(100))
    remarks = db.Column(db.Text)
    
    items = db.relationship('GRNItem', backref='grn', lazy=True, cascade="all, delete-orphan")

class GRNItem(db.Model):
    __tablename__ = 'grn_items'
    id = db.Column(db.Integer, primary_key=True)
    grn_id = db.Column(db.Integer, db.ForeignKey('grns.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_received = db.Column(db.Integer, nullable=False)
    batch_number = db.Column(db.String(50))
    expiry_date = db.Column(db.Date)

class PurchaseInvoice(db.Model):
    """Vendor Bill / Purchase Invoice"""
    __tablename__ = 'purchase_invoices'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='UNPAID') # 'UNPAID', 'PARTIAL', 'PAID'
    
    payments = db.relationship('VendorPayment', backref='invoice', lazy=True)
    vendor = db.relationship('Vendor', backref='purchase_invoices', lazy=True)

class VendorPayment(db.Model):
    """Payment to Vendor"""
    __tablename__ = 'vendor_payments'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('purchase_invoices.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_mode = db.Column(db.String(20), nullable=False) # 'Cash', 'Bank', 'UPI', 'NEFT'
    transaction_id = db.Column(db.String(100))
    remarks = db.Column(db.Text)
