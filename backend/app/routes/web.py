"""
Web routes for serving HTML pages.
"""
from flask import Blueprint, render_template, redirect, url_for

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """Root: redirect to electoral campaign team dashboard."""
    return redirect(url_for('web.campaign_team_dashboard'))


@web_bp.route('/campaign-team')
def campaign_team_dashboard():
    """Serve Campaign Team Dashboard (front-only branch: no access gate)."""
    try:
        return render_template('campaign_team_dashboard.html')
    except Exception as e:
        return {
            'error': 'Template not found',
            'message': 'Campaign team dashboard template not available',
            'details': str(e)
        }, 404
