"""
Email Service for ERP System using Resend API
Handles all email notifications including:
- Low stock alerts
- Order confirmations (Purchase & Sales)
- Daily/Weekly reports
"""

import resend
from flask import current_app, render_template_string
from datetime import datetime
from io import BytesIO

class EmailService:
    """Email notification service using Resend API"""

    @staticmethod
    def generate_pdf(html_content):
        """Generate a simple PDF from HTML content using reportlab (no system deps)"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            import re

            output = BytesIO()
            c = canvas.Canvas(output, pagesize=A4)
            # Strip HTML tags for plain text rendering
            text = re.sub(r'<[^>]+>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text).strip()
            width, height = A4
            c.setFont("Helvetica", 11)
            y = height - 50
            for line in text.split('. '):
                if y < 50:
                    c.showPage()
                    y = height - 50
                c.drawString(40, y, line.strip()[:100])
                y -= 20
            c.save()
            return output.getvalue()
        except Exception as e:
            print(f"[ERROR] PDF generation failed: {e}")
            return None
    
    @staticmethod
    def _get_recipient_emails():
        """Fetch all active user emails from the database"""
        from app.models import User
        try:
            users = User.query.filter_by(is_active=True).all()
            emails = [u.email for u in users if u.email]
            return emails if emails else []
        except Exception as e:
            print(f"[RECOVERY] Failed to fetch users: {e}")
            from app.models import Setting
            return [Setting.get('ADMIN_EMAIL', current_app.config.get('ADMIN_EMAIL'))]

    @staticmethod
    def _send_email(to_email, subject, html_content, attachments=None):
        """Internal method to send email via Resend"""
        from app.models import Setting
        try:
            enable_notifications = Setting.get('ENABLE_EMAIL_NOTIFICATIONS', current_app.config.get('ENABLE_EMAIL_NOTIFICATIONS'))
            
            if not enable_notifications:
                print(f"Email notifications disabled. Would send: {subject} to {to_email}")
                return False
            
            api_key = Setting.get('RESEND_API_KEY', current_app.config.get('RESEND_API_KEY'))
            resend.api_key = api_key
            
            # If to_email is None or empty, use the broadcast list
            if not to_email:
                recipients = EmailService._get_recipient_emails()
            elif isinstance(to_email, list):
                recipients = to_email
            else:
                recipients = [to_email]

            if not recipients:
                print("[WARNING] No recipients found for email.")
                return False

            sender = Setting.get('EMAIL_FROM', current_app.config.get('EMAIL_FROM'))
            admin_email = Setting.get('ADMIN_EMAIL', current_app.config.get('ADMIN_EMAIL'))

            # --- Sandbox Safety Layer ---
            # Resend sandbox (onboarding@resend.dev) ONLY allows sending to the single verified email.
            # If we try to broadcast to others, the entire request fails.
            if 'onboarding@resend.dev' in sender:
                print(f"[SANDBOX] Restricted sender detected. Filtering recipients to verified email: {admin_email}")
                recipients = [admin_email]
            
            params = {
                "from": sender,
                "to": recipients,
                "subject": subject,
                "html": html_content,
                "attachments": attachments or []
            }
            
            email = resend.Emails.send(params)
            print(f"[SUCCESS] Broadcast email sent to {len(recipients)} users: {subject}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Email sending failed: {str(e)}")
            return False
    
    @staticmethod
    def send_low_stock_alert(products):
        """Send low stock alert email"""
        from app.models import Setting
        low_stock_enabled = Setting.get('LOW_STOCK_EMAIL_ENABLED', current_app.config.get('LOW_STOCK_EMAIL_ENABLED'))
        if not low_stock_enabled:
            return
        
        html = f"""
        <h2>⚠️ Low Stock Alert - ERP System</h2>
        <p>The following products are running low on stock:</p>
        <table border="1" cellpadding="10" style="border-collapse: collapse;">
            <thead style="background-color: #f8d7da;">
                <tr>
                    <th>Product Code</th>
                    <th>Product Name</th>
                    <th>Current Stock</th>
                    <th>Minimum Required</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for product in products:
            html += f"""
                <tr>
                    <td>{product.code}</td>
                    <td>{product.name}</td>
                    <td style="color: red; font-weight: bold;">{product.stock_quantity}</td>
                    <td>{product.min_stock_alert}</td>
                </tr>
            """
        
        html += """
            </tbody>
        </table>
        <p><strong>Action Required:</strong> Please reorder these items to maintain inventory levels.</p>
        <p style="color: #666; font-size: 12px;">Generated on: """ + datetime.now().strftime('%Y-%m-%d %I:%M %p') + """</p>
        """
        
        # Broadcast to all registered users
        EmailService._send_email(
            None, # Passing None triggers the broadcast list in _send_email
            f"🚨 Low Stock Alert - {len(products)} Products",
            html
        )
    
    @staticmethod
    def send_purchase_order_confirmation(order, vendor):
        """Send purchase order confirmation email"""
        from app.models import Setting
        order_email_enabled = Setting.get('ORDER_EMAIL_ENABLED', current_app.config.get('ORDER_EMAIL_ENABLED'))
        if not order_email_enabled:
            return
        
        items_html = ""
        for item in order.items:
            items_html += f"""
                <tr>
                    <td>{item.product.code}</td>
                    <td>{item.product.name}</td>
                    <td>{item.quantity}</td>
                    <td>₹{item.price:.2f}</td>
                    <td>₹{item.total:.2f}</td>
                </tr>
            """
        
        html = f"""
        <h2>✅ Purchase Order Confirmation</h2>
        <p><strong>Order ID:</strong> PO-{order.id}</p>
        <p><strong>Vendor:</strong> {vendor.name}</p>
        <p><strong>Date:</strong> {order.date.strftime('%Y-%m-%d %I:%M %p')}</p>
        <p><strong>Status:</strong> <span style="background-color: #28a745; color: white; padding: 4px 8px; border-radius: 4px;">{order.status}</span></p>
        
        <h3>Order Items</h3>
        <table border="1" cellpadding="10" style="border-collapse: collapse; width: 100%;">
            <thead style="background-color: #007bff; color: white;">
                <tr>
                    <th>Code</th>
                    <th>Product</th>
                    <th>Quantity</th>
                    <th>Price</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
            <tfoot>
                <tr style="background-color: #f0f0f0; font-weight: bold;">
                    <td colspan="4" align="right">Grand Total:</td>
                    <td>₹{order.grand_total:.2f}</td>
                </tr>
            </tfoot>
        </table>
        
        <p style="margin-top: 20px;"><strong>✅ Stock has been automatically updated.</strong></p>
        <p style="color: #666; font-size: 12px;">This is an automated notification from ERP System.</p>
        """
        
        # Broadcast to all registered users
        EmailService._send_email(
            None,
            f"Purchase Order Confirmed - PO-{order.id}",
            html
        )
    
    @staticmethod
    def send_daily_summary():
        """Send daily summary report email"""
        from app.models import Product, Order, Setting
        from sqlalchemy import func
        from datetime import date
        
        daily_reports_enabled = Setting.get('DAILY_REPORT_EMAIL_ENABLED', current_app.config.get('DAILY_REPORT_EMAIL_ENABLED'))
        if not daily_reports_enabled:
            return
        
        today = date.today()
        
        # Today's stats
        from app import db
        
        today_purchases = db.session.query(func.sum(Order.total_amount)).filter(
            Order.type == 'PURCHASE',
            func.date(Order.date) == today
        ).scalar() or 0
        
        low_stock_count = Product.query.filter(
            Product.stock_quantity <= Product.min_stock_alert
        ).count()
        
        total_products = Product.query.count()
        
        html = f"""
        <h2>📊 Daily Summary Report - {today.strftime('%d %B %Y')}</h2>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3>Key Metrics</h3>
            <table style="width: 100%;">
                <tr>
                    <td style="padding: 10px;">
                        <strong>🛒 Today's Purchases:</strong>
                    </td>
                    <td style="padding: 10px; text-align: right; font-size: 20px; color: #ffc107;">
                        ₹{today_purchases:.2f}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px;">
                        <strong>⚠️ Low Stock Items:</strong>
                    </td>
                    <td style="padding: 10px; text-align: right; font-size: 20px; color: #dc3545;">
                        {low_stock_count}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px;">
                        <strong>📦 Total Products:</strong>
                    </td>
                    <td style="padding: 10px; text-align: right; font-size: 20px; color: #007bff;">
                        {total_products}
                    </td>
                </tr>
            </table>
        </div>
        
        <p><strong>Access your ERP Dashboard:</strong> <a href="http://127.0.0.1:5000">Login to ERP</a></p>
        <p style="color: #666; font-size: 12px;">This is an automated daily report from your ERP System.</p>
        """
        
        # Broadcast to all registered users
        EmailService._send_email(
            None,
            f"📊 Daily Report - {today.strftime('%d %b %Y')}",
            html
        )
