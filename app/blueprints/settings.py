from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app.models import Setting
from app import db
from app.decorators import role_required

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin')
def general():
    if request.method == 'POST':
        # List of expected keys
        keys = ['company_name', 'company_address', 'company_phone', 'company_email', 'company_gstin', 'terms_conditions']
        
        for key in keys:
            val = request.form.get(key)
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = val
            else:
                setting = Setting(key=key, value=val)
                db.session.add(setting)
        
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings.general'))

    # Load all settings into a dict
    settings_list = Setting.query.all()
    settings = {s.key: s.value for s in settings_list}
    
    return render_template('settings/general.html', settings=settings)

@settings_bp.route('/settings/notifications', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'admin')
def notifications():
    if request.method == 'POST':
        keys = [
            'ENABLE_EMAIL_NOTIFICATIONS', 
            'LOW_STOCK_EMAIL_ENABLED', 
            'ORDER_EMAIL_ENABLED', 
            'DAILY_REPORT_EMAIL_ENABLED',
            'RESEND_API_KEY',
            'ADMIN_EMAIL',
            'EMAIL_FROM'
        ]
        
        for key in keys:
            if key.endswith('_ENABLED') or key == 'ENABLE_EMAIL_NOTIFICATIONS':
                val = 'True' if request.form.get(key) == 'on' else 'False'
            else:
                val = request.form.get(key)
                
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = val
            else:
                setting = Setting(key=key, value=val)
                db.session.add(setting)
        
        db.session.commit()
        flash('Notification settings updated!', 'success')
        return redirect(url_for('settings.notifications'))

    settings_list = Setting.query.all()
    settings = {s.key: s.value for s in settings_list}
    
    return render_template('settings/notifications.html', settings=settings)

@settings_bp.app_context_processor
def inject_settings():
    try:
        # Use simple caching or just query (low load assumed)
        settings_list = Setting.query.all()
        company_settings = {s.key: s.value for s in settings_list}
        # Provide defaults if empty
        if not company_settings.get('company_name'):
            company_settings['company_name'] = 'Gharana Gold'
        return dict(company=company_settings)
    except Exception:
        return dict(company={})
