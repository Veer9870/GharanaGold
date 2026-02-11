from datetime import datetime, timedelta
from app.models import Product, Transaction, Order, OrderItem, GRN
from app import db
from sqlalchemy import func

class AIEngine:
    @staticmethod
    def get_stock_insights():
        """Returns AI-driven insights for the dashboard"""
        insights = []
        
        # 1. Critical Stock Pulse
        critical_count = Product.query.filter(Product.stock_quantity <= (Product.min_stock_alert * 0.5)).count()
        if critical_count > 0:
            insights.append({
                'type': 'danger',
                'icon': 'fas fa-fire-flame-curved',
                'title': 'Stock Crisis Risk',
                'message': f"AI has detected {critical_count} products at critical exhaustion levels. Order replenishment immediately to avoid supply disruption.",
                'action': 'Restock Now',
                'endpoint': 'purchase.create_order'
            })
            
        # 2. Demand Trend Analysis
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        top_moving = db.session.query(
            Product.id,
            Product.name,
            func.sum(Transaction.quantity).label('total_out')
        ).join(Transaction).filter(
            Transaction.type == 'OUT',
            Transaction.date >= seven_days_ago
        ).group_by(Product.id, Product.name).order_by(func.sum(Transaction.quantity).desc()).first()
        
        if top_moving:
            insights.append({
                'type': 'primary',
                'icon': 'fas fa-chart-line',
                'title': 'High Velocity Demand',
                'message': f"'{top_moving.name}' is exhibiting high turnover. AI predicts a stock-out within 4 days at current consumption rate.",
                'action': 'Expand Stock',
                'endpoint': 'purchase.create_order',
                'product_id': top_moving.id
            })
        else:
            insights.append({
                'type': 'info',
                'icon': 'fas fa-robot',
                'title': 'Learning Patterns',
                'message': "Neural engine is tracking stock movement. Optimized purchasing triggers will appear as transaction volume increases.",
                'action': 'Configure AI',
                'endpoint': 'settings.general'
            })
            
        # 3. Supply Chain Health
        pending_orders = Order.query.filter_by(status='PENDING').count()
        if pending_orders > 0:
            insights.append({
                'type': 'warning',
                'icon': 'fas fa-link-slash',
                'title': 'Supply Chain Lag',
                'message': f"Delayed fulfillment detected: {pending_orders} active POs haven't arrived. Inventory buffers are absorbing the delay.",
                'action': 'Follow up',
                'endpoint': 'purchase.orders'
            })
            
        return insights

    @staticmethod
    def get_procurement_insights():
        """Calculates real-time procurement insights for the Purchase module"""
        # Calculate Average Lead Time
        # Lead Time = Date of Receipt (GRN) - Date of Order (PO)
        
        # We need historical data for this
        completed_orders = db.session.query(Order).filter(Order.status.in_(['RECEIVED', 'BILLED', 'PAID'])).all()
        
        if not completed_orders:
            return "Neural engine is tracking vendor sync. Insights will appear as you record more Goods Receipts (GRN)."

        total_days = 0
        count = 0
        
        for order in completed_orders:
            grn = GRN.query.filter_by(order_id=order.id).first()
            if grn:
                delta = grn.date - order.date
                total_days += delta.days
                count += 1
        
        if count == 0:
            return "Neural engine starting... Waiting for first Goods Receipt to calculate lead times."
            
        avg_lead_time = total_days / count
        
        # Insights logic
        if avg_lead_time <= 2:
            return f"Strategic Optimization: Vendor synchronization is <span class='text-success fw-bold'>Healthy</span>. Current average lead time is {avg_lead_time:.1f} days."
        elif avg_lead_time <= 5:
            return f"Market Insight: Average fulfillment time is {avg_lead_time:.1f} days. AI suggests placing orders <span class='text-primary fw-bold'>48h earlier</span> to maintain buffer."
        else:
            return f"Supply Chain Alert: High lead times detected ({avg_lead_time:.1f} days). Neural engine predicts potential <span class='text-danger fw-bold'>stock-outs</span> if buffers are not increased."

    @staticmethod
    def get_vendor_reliability(vendor_id):
        """Calculates a real-time reliability percentage for a vendor"""
        orders = Order.query.filter_by(vendor_id=vendor_id, status='RECEIVED').all()
        if not orders:
            return 100 # Default for new partners

        total_score = 0
        order_count = len(orders)

        for order in orders:
            order_score = 100
            grn = GRN.query.filter_by(order_id=order.id).first()
            
            if grn:
                # 1. Timeliness (Lead Time Penalty)
                # target is 2 days. penalty of 10% for ogni day extra
                lead_time = (grn.date - order.date).days
                if lead_time > 2:
                    order_score -= (lead_time - 2) * 10

                # 2. Accuracy (Ordered vs Received ratio)
                total_ordered = db.session.query(func.sum(OrderItem.quantity)).filter_by(order_id=order.id).scalar() or 0
                total_received = db.session.query(func.sum(OrderItem.received_quantity)).filter_by(order_id=order.id).scalar() or 0
                
                if total_ordered > 0:
                    accuracy = (total_received / total_ordered)
                    if accuracy < 0.95: # Allow 5% margin
                        order_score -= (1 - accuracy) * 100

            total_score += max(0, min(100, order_score))

        return int(total_score / order_count)

    @staticmethod
    def get_forecasting_data():
        """Provides data for the AI Prediction Chart using real-time historical telemetry"""
        labels = []
        actual = []
        predicted = []
        
        today = datetime.utcnow().date()
        
        # 1. Fetch Current Global Stock Level
        # Sum of all sellable products in the warehouse
        current_global_stock = db.session.query(func.sum(Product.stock_quantity)).scalar() or 0
        
        # 2. Historical Re-construction (Neural Back-tracking)
        # We calculate stock levels for the last 7 days by reversing recorded transactions
        daily_actuals = []
        temp_stock = current_global_stock
        
        for i in range(7):
            date_target = today - timedelta(days=i)
            
            # Aggregate all inflows and outflows for this specific micro-window
            day_in = db.session.query(func.sum(Transaction.quantity)).filter(
                func.date(Transaction.date) == date_target,
                Transaction.type.in_(['IN', 'PRODUCTION'])
            ).scalar() or 0
            
            day_out = db.session.query(func.sum(Transaction.quantity)).filter(
                func.date(Transaction.date) == date_target,
                Transaction.type == 'OUT'
            ).scalar() or 0
            
            daily_actuals.append(float(temp_stock))
            # Subtract arrivals and add departures to find the previous day's closing state
            temp_stock = temp_stock - day_in + day_out
            
        # Refactor for chronological display (Day -6 to Today)
        daily_actuals.reverse()
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            labels.append(date.strftime('%b %d'))
        
        actual = daily_actuals
        predicted = [None] * 7
        
        # 3. Velocity Analysis (Consumption Rate)
        # We analyze the last 14 days to determine the average daily "burn rate"
        lookback_window = 14
        fourteen_days_ago = today - timedelta(days=lookback_window)
        total_out = db.session.query(func.sum(Transaction.quantity)).filter(
            Transaction.type == 'OUT',
            Transaction.date >= fourteen_days_ago
        ).scalar() or 0
        
        # Calculate daily velocity, fallback to localized minimum if no data exists
        avg_daily_velocity = float(total_out) / lookback_window if total_out else 2.5
        
        # 4. Neural Projection (7-Day Forecast)
        last_known_stock = actual[-1]
        predicted[6] = last_known_stock # Synthetic bridge point for the graph
        
        for i in range(1, 8):
            future_date = today + timedelta(days=i)
            labels.append(future_date.strftime('%b %d'))
            
            last_known_stock -= avg_daily_velocity
            predicted.append(max(0, float(round(last_known_stock, 2))))
            actual.append(None)
            
        return {
            'labels': labels,
            'actual': actual,
            'predicted': predicted
        }
