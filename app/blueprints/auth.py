from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app import db
from urllib.parse import urlparse

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Please check your login details and try again.', 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=remember)
        
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.dashboard')
        
        return redirect(next_page)
        
    return render_template('auth/login.html', title='Login')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/users')
@login_required
def users():
    # Only for admin
    if not current_user.has_role('super_admin', 'admin'):
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    all_users = User.query.all()
    return render_template('auth/users.html', users=all_users, title='User Management')

@auth_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    # Only for admin
    if not current_user.has_role('super_admin', 'admin'):
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('auth.users'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('auth.add_user'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.add_user'))
            
        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'User {username} created successfully.', 'success')
            return redirect(url_for('auth.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
            
    return render_template('auth/register.html', title='Provision Account')

@auth_bp.route('/audit')
@login_required
def audit_logs():
    # Only for admin
    if not current_user.has_role('super_admin', 'admin'):
        flash('Access Denied', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Fetch recent activities
    from app.models import Transaction, Order
    from sqlalchemy import desc
    
    # Inventory movements
    movements = db.session.query(Transaction).order_by(desc(Transaction.date)).limit(50).all()
    
    # System orders
    orders = db.session.query(Order).order_by(desc(Order.date)).limit(50).all()
    
    return render_template('auth/audit.html', 
                          movements=movements, 
                          orders=orders,
                          title='System Audit Logs')

@auth_bp.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    # Only super_admin or admin can edit? Let's restrict high levl ops to super_admin or both
    if not current_user.has_role('super_admin', 'admin'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('auth.users'))
        
    user = User.query.get_or_404(id)
    
    if request.method == 'POST':
        # Prevent demoting self if only super_admin? Logic can be complex. keeping simple.
        
        user.role = request.form.get('role')
        user.is_active = True if request.form.get('is_active') == 'on' else False
        
        password = request.form.get('password')
        if password and password.strip():
            user.set_password(password)
            
        try:
            db.session.commit()
            flash(f'User {user.username} updated successfully.', 'success')
            return redirect(url_for('auth.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Update failed: {str(e)}', 'danger')
            
    return render_template('auth/edit_user.html', user=user)

@auth_bp.route('/users/delete/<int:id>')
@login_required
def delete_user(id):
    if not current_user.has_role('super_admin'):
        flash('Only Super Admin can delete users.', 'danger')
        return redirect(url_for('auth.users'))
    
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Cannot delete active self session.', 'danger')
        return redirect(url_for('auth.users'))
        
    try:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted.', 'success')
    except Exception as e:
        flash(f'Deletion failed: {str(e)}', 'danger')
        
    return redirect(url_for('auth.users'))
