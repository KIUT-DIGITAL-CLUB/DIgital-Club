"""
Verification routes for digital ID cards
Public routes for verifying member IDs
"""

from flask import Blueprint, render_template, abort
from app.models import Member

verification_bp = Blueprint('verification', __name__)


@verification_bp.route('/verify-id/<member_id_number>')
def verify_id(member_id_number):
    """
    Public verification page for member IDs
    Anyone can scan QR code and verify membership
    """
    member = Member.query.filter_by(member_id_number=member_id_number).first()
    
    if not member:
        # Invalid ID
        return render_template('verification.html', 
                             valid=False, 
                             member_id=member_id_number)
    
    # Valid member found
    return render_template('verification.html',
                         valid=True,
                         member=member,
                         member_id=member_id_number)

