#!/usr/bin/env python3
"""
Migration script for Super Admin System
Adds is_super_admin field and marks admin@digitalclub.kiut.ac.tz as super admin
"""

import sys
import os
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User

def migrate_super_admin():
    """Add is_super_admin field and mark default admin as super admin"""
    print("Starting Super Admin migration...")
    
    try:
        # Add is_super_admin column to User table
        print("Adding is_super_admin column to User table...")
        
        # Check if column already exists
        inspector = db.inspect(db.engine)
        columns = [column['name'] for column in inspector.get_columns('user')]
        
        if 'is_super_admin' not in columns:
            # Add the column using raw SQL
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE'))
                conn.commit()
            print("Added is_super_admin column successfully!")
        else:
            print("is_super_admin column already exists, skipping...")
        
        # Mark admin@digitalclub.kiut.ac.tz as super admin
        print("Marking admin@digitalclub.kiut.ac.tz as super admin...")
        admin_user = User.query.filter_by(email='admin@digitalclub.kiut.ac.tz').first()
        
        if admin_user:
            admin_user.is_super_admin = True
            admin_user.role = 'admin'  # Ensure role is admin
            admin_user.is_approved = True  # Ensure approved
            db.session.commit()
            print(f"Super admin status set for: {admin_user.email}")
        else:
            print("Admin user not found! Creating super admin...")
            admin_user = User(
                email='admin@digitalclub.kiut.ac.tz',
                role='admin',
                is_approved=True,
                is_super_admin=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("Super admin user created: admin@digitalclub.kiut.ac.tz / admin123")
        
        # Ensure all other users are not super admin
        print("Ensuring other users are not super admin...")
        other_users = User.query.filter(User.email != 'admin@digitalclub.kiut.ac.tz').all()
        for user in other_users:
            if user.is_super_admin:
                user.is_super_admin = False
                print(f"Removed super admin status from: {user.email}")
        
        db.session.commit()
        
        print("\nSuper Admin migration completed successfully!")
        print("\nSummary:")
        print(f"- Super admin: admin@digitalclub.kiut.ac.tz")
        print(f"- Total users: {User.query.count()}")
        print(f"- Admin users: {User.query.filter_by(role='admin').count()}")
        print(f"- Super admin users: {User.query.filter_by(is_super_admin=True).count()}")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        db.session.rollback()
        raise

def main():
    """Main migration function"""
    app = create_app()
    with app.app_context():
        migrate_super_admin()

if __name__ == '__main__':
    main()
