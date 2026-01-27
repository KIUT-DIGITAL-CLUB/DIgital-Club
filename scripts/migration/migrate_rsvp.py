#!/usr/bin/env python3
"""
Database migration script for RSVP functionality
Run this script to add the RSVP table to your database
"""

from app import create_app, db
from app.models import RSVP

def migrate_database():
    """Add RSVP table to the database"""
    app = create_app()
    
    with app.app_context():
        try:
            # Create the RSVP table
            db.create_all()
            print("✅ Database migration completed successfully!")
            print("✅ RSVP table has been created.")
            
            # Check if RSVP table exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'rsvp' in tables:
                print("✅ RSVP table verified in database.")
            else:
                print("❌ RSVP table not found. Please check your database connection.")
                
        except Exception as e:
            print(f"❌ Database migration failed: {e}")
            return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting database migration for RSVP functionality...")
    success = migrate_database()
    
    if success:
        print("\n🎉 Migration completed! You can now:")
        print("   1. Create events in the admin panel")
        print("   2. Members can RSVP to events")
        print("   3. Admins can approve/reject RSVPs in bulk")
        print("   4. Email/SMS notifications will be sent automatically")
        print("\n📧 Don't forget to configure email/SMS credentials in config.py")
    else:
        print("\n❌ Migration failed. Please check the error messages above.")
