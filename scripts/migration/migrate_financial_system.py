#!/usr/bin/env python3
"""
Migration script for Financial Management System
Creates new tables and sets up default categories
"""

import sys
import os
from datetime import datetime, date

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import FinancialPeriod, FinancialCategory, FinancialTransaction, MembershipPayment, User

def create_default_categories():
    """Create default financial categories"""
    print("Creating default financial categories...")
    
    # Default revenue categories
    revenue_categories = [
        ("Membership Fees", "Membership fee payments from members"),
        ("Event Revenue", "Revenue from events, workshops, and activities"),
        ("Sponsorships", "Sponsorship money from companies and organizations"),
        ("Donations", "Donations from alumni and supporters"),
        ("Other Revenue", "Other sources of income")
    ]
    
    # Default expense categories
    expense_categories = [
        ("Equipment", "Purchase of equipment, hardware, and software"),
        ("Venue Costs", "Rental costs for venues and meeting spaces"),
        ("Event Costs", "Costs for organizing events and workshops"),
        ("Marketing", "Marketing materials, advertising, and promotion"),
        ("Administrative", "Administrative costs and office supplies"),
        ("Other Expenses", "Other operational expenses")
    ]
    
    # Create revenue categories
    for name, description in revenue_categories:
        existing = FinancialCategory.query.filter_by(name=name, type='revenue').first()
        if not existing:
            category = FinancialCategory(
                name=name,
                type='revenue',
                description=description,
                is_builtin=True,
                is_active=True
            )
            db.session.add(category)
            print(f"  Created revenue category: {name}")
    
    # Create expense categories
    for name, description in expense_categories:
        existing = FinancialCategory.query.filter_by(name=name, type='expense').first()
        if not existing:
            category = FinancialCategory(
                name=name,
                type='expense',
                description=description,
                is_builtin=True,
                is_active=True
            )
            db.session.add(category)
            print(f"  Created expense category: {name}")
    
    db.session.commit()
    print("Default categories created successfully!")

def create_default_period():
    """Create a default financial period for existing data"""
    print("Creating default financial period...")
    
    # Check if any periods already exist
    existing_periods = FinancialPeriod.query.count()
    if existing_periods > 0:
        print("Financial periods already exist, skipping default period creation.")
        return
    
    # Create a default period covering the last year
    end_date = date.today()
    start_date = date(end_date.year - 1, 1, 1)
    
    # Get the first admin user to be the opener
    admin_user = User.query.filter_by(role='admin').first()
    if not admin_user:
        print("No admin user found! Please create an admin user first.")
        return
    
    default_period = FinancialPeriod(
        name="Default Period (Historical Data)",
        start_date=start_date,
        end_date=end_date,
        status='closed',  # Mark as closed since it's historical
        description="Default period created during migration to capture historical data",
        opened_by=admin_user.id,
        closed_by=admin_user.id,
        closed_at=datetime.utcnow()
    )
    
    db.session.add(default_period)
    db.session.commit()
    
    # Link existing payments to this period
    payments_count = MembershipPayment.query.filter_by(financial_period_id=None).count()
    if payments_count > 0:
        MembershipPayment.query.filter_by(financial_period_id=None).update({
            'financial_period_id': default_period.id
        })
        db.session.commit()
        print(f"Linked {payments_count} existing payments to default period")
    
    print(f"Created default period: {default_period.name}")

def migrate_existing_payments():
    """Create financial transactions for existing membership payments"""
    print("Creating financial transactions for existing payments...")
    
    # Get membership fees category
    membership_category = FinancialCategory.query.filter_by(name='Membership Fees', type='revenue').first()
    if not membership_category:
        print("Membership Fees category not found!")
        return
    
    # Get the default period
    default_period = FinancialPeriod.query.filter_by(name="Default Period (Historical Data)").first()
    if not default_period:
        print("Default period not found!")
        return
    
    # Create transactions for payments that don't have them
    payments_without_transactions = db.session.query(MembershipPayment).outerjoin(
        FinancialTransaction, 
        db.and_(
            FinancialTransaction.reference_type == 'payment',
            FinancialTransaction.reference_id == MembershipPayment.id
        )
    ).filter(FinancialTransaction.id.is_(None)).all()
    
    transactions_created = 0
    for payment in payments_without_transactions:
        # Check if transaction already exists
        existing_transaction = FinancialTransaction.query.filter_by(
            reference_type='payment',
            reference_id=payment.id
        ).first()
        
        if not existing_transaction:
            transaction = FinancialTransaction(
                financial_period_id=payment.financial_period_id or default_period.id,
                category_id=membership_category.id,
                transaction_type='revenue',
                amount=payment.amount,
                transaction_date=payment.payment_date,
                description=f"Membership fee payment from {payment.member.full_name}",
                notes=f"Payment method: {payment.payment_method or 'Not specified'}",
                reference_type='payment',
                reference_id=payment.id,
                recorded_by=payment.recorded_by
            )
            db.session.add(transaction)
            transactions_created += 1
    
    db.session.commit()
    print(f"Created {transactions_created} financial transactions for existing payments")

def main():
    """Main migration function"""
    print("Starting Financial Management System migration...")
    
    app = create_app()
    with app.app_context():
        try:
            # Create tables
            print("Creating database tables...")
            db.create_all()
            print("Database tables created successfully!")
            
            # Create default categories
            create_default_categories()
            
            # Create default period
            create_default_period()
            
            # Migrate existing payments
            migrate_existing_payments()
            
            print("\nMigration completed successfully!")
            print("\nNext steps:")
            print("1. Start your Flask application")
            print("2. Go to Admin Panel > Financial Management")
            print("3. Create a new financial period for current leadership")
            print("4. Begin recording new transactions")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    main()
