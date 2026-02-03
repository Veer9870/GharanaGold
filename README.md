
# Enterprise ERP System

A complete, production-ready ERP system built with Flask, MySQL/SQLite, and Bootstrap 5 for FMCG/Food Manufacturing companies.


## Features

### 🔐 Authentication & User Management
- Session-based login with password hashing
- Role-based access control (Super Admin, Admin, Manager, Store User)
- Permission-based menu visibility

### 📊 Dashboard
- Real-time metrics (Total Products, Stock Value, Low Stock Alerts, Sales)
- Visual analytics placeholder
- Quick action shortcuts

### 📦 Inventory Management
- Product Master with auto-generated codes
- Category, Brand, Unit management
- Cost Price & Selling Price with GST
- Real-time stock tracking
- Low stock alerts
- Batch number & Expiry date tracking
- Warehouse location management

### 🛒 Purchase Module
- Supplier Master (Contact, GSTIN)
- Purchase Order creation
- Automatic stock increment on purchase
- Purchase history tracking

### 💰 Sales Module
- Customer Master
- Sales Order creation
- GST-inclusive invoice generation
- Automatic stock deduction
- Discount handling
- Printable invoices

### 📈 Reports & Analytics
- Inventory Report (CSV Export)
- Sales Report (CSV Export)
- Purchase Report (CSV Export)
- Low stock alerts

### ⚙️ Settings
- Company Profile configuration
- GST Settings
- Financial Year setup

## Tech Stack

- **Backend**: Python 3.x, Flask
- **Database**: SQLite (default) / MySQL (production)
- **ORM**: SQLAlchemy
- **Frontend**: Bootstrap 5, Jinja2
- **Authentication**: Flask-Login, Werkzeug Security

## Project Structure

```
ERP/
├── app/
│   ├── __init__.py           # App factory
│   ├── models.py             # Database models
│   ├── decorators.py         # Role-based access decorators
│   ├── blueprints/
│   │   ├── main.py          # Dashboard & Settings
│   │   ├── auth.py          # Authentication
│   │   ├── inventory.py     # Inventory management
│   │   ├── purchase.py      # Purchase orders
│   │   ├── sales.py         # Sales orders
│   │   └── reports.py       # Reports & exports
│   ├── templates/
│   │   ├── base.html
│   │   ├── sidebar.html
│   │   ├── navbar.html
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── inventory/
│   │   ├── purchase/
│   │   ├── sales/
│   │   └── reports/
│   └── static/
│       ├── css/
│       ├── js/
│       └── img/
├── config.py                 # Configuration
├── run.py                    # Application entry point
├── setup_db.py              # Database initialization
├── requirements.txt         # Python dependencies
└── README.md
```

## Installation & Setup

### 1. Prerequisites
- Python 3.8+
- pip
- MySQL (optional, for production)

### 2. Clone & Install Dependencies

```bash
cd ERP
pip install -r requirements.txt
```

### 3. Database Setup

**Option A: SQLite (Default - for development)**
```bash
python setup_db.py
```

**Option B: MySQL (for production)**

1. Update `config.py`:
```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://username:password@localhost/erp_db'
```

2. Install MySQL driver:
```bash
pip install pymysql
```

3. Create database:
```sql
CREATE DATABASE erp_db;
```

4. Run setup:
```bash
python setup_db.py
```

### 4. Run the Application

```bash
python run.py
```

Visit: `http://127.0.0.1:5000`

## Default Login Credentials

| Username | Password   | Role         |
|----------|------------|--------------|
| admin    | admin123   | Super Admin  |
| manager  | manager123 | Manager      |

**⚠️ IMPORTANT**: Change these passwords immediately in production!

## Usage Guide

### Adding Products
1. Navigate to **Inventory** → **Add New Product**
2. Fill in product details (Code, Name, Category, Prices, Stock)
3. Set minimum stock alert level
4. Save

### Creating Purchase Order
1. Go to **Purchase** → **New PO**
2. Select Supplier
3. Add items with quantity and cost
4. Submit → Stock automatically increases

### Processing Sales
1. Navigate to **Sales** → **New Sale**
2. Select Customer
3. Add products (only in-stock items shown)
4. Apply discount if needed
5. Generate Invoice → Stock automatically decreases
6. Print invoice for customer

### Generating Reports
1. Go to **Reports**
2. Select report type (Inventory/Sales/Purchase)
3. Click **Download CSV**

## Security Features

✅ Password hashing (Werkzeug)  
✅ Session-based authentication  
✅ Role-based access control  
✅ SQL Injection prevention (SQLAlchemy ORM)  
✅ CSRF protection (Flask-WTF)

## Production Deployment (Linux)

### 1. Install Gunicorn
```bash
pip install gunicorn
```

### 2. Run with Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:8000 run:app
```

### 3. Setup Nginx (Optional)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Environment Variables
```bash
export FLASK_CONFIG=production
export SECRET_KEY=your-super-secret-key-change-this
export DATABASE_URL=mysql+pymysql://user:pass@localhost/erp_db
```

### 5. Systemd Service (Optional)
Create `/etc/systemd/system/erp.service`:
```ini
[Unit]
Description=ERP System
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/ERP
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 run:app

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable erp
sudo systemctl start erp
```

## Database Schema

### Core Tables
- **users**: Authentication & roles
- **settings**: System configuration
- **products**: Inventory master
- **suppliers**: Supplier directory
- **customers**: Customer directory
- **orders**: Purchase & Sales orders
- **order_items**: Order line items
- **transactions**: Stock movement history

## Customization

### Adding New Roles
Edit `app/models.py`:
```python
role = db.Column(db.String(20), nullable=False, default='your_new_role')
```

### Changing Company Info
1. Login as Admin
2. Go to **Settings**
3. Update Company Name, Address, GST, etc.

## Troubleshooting

**Issue**: Database locked error  
**Solution**: SQLite doesn't support concurrent writes. Use MySQL for production.

**Issue**: Module not found errors  
**Solution**: Ensure all dependencies are installed: `pip install -r requirements.txt`

**Issue**: Permission denied on certain pages  
**Solution**: Check user role. Some pages require Admin/Manager access.

## License

This project is built as a demonstration ERP system. Modify as needed for your business requirements.

## Support

For issues or questions, please check the code comments or create an issue in the repository.

---

**Built with ❤️ for FMCG/Food Manufacturing Industry**

