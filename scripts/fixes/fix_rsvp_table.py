#!/usr/bin/env python3
"""
Database migration script to fix RSVP table structure
This script updates the member_id column to be nullable
"""

from app import create_app, db
from sqlalchemy import text

def fix_rsvp_table():
    """Fix RSVP table structure"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if RSVP table exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'rsvp' not in tables:
                print("❌ RSVP table not found. Creating it...")
                db.create_all()
                print("✅ RSVP table created successfully!")
                return True
            
            # Check if member_id column is nullable
            columns = inspector.get_columns('rsvp')
            member_id_column = next((col for col in columns if col['name'] == 'member_id'), None)
            
            if member_id_column and not member_id_column['nullable']:
                print("🔧 Fixing member_id column to be nullable...")
                
                # For SQLite, we need to recreate the table
                # First, create a backup of existing data
                with db.engine.connect() as conn:
                    # Get existing data
                    result = conn.execute(text("SELECT * FROM rsvp"))
                    existing_data = result.fetchall()
                    columns_info = result.keys()
                    
                    print(f"📊 Found {len(existing_data)} existing RSVP records")
                    
                    # Drop the old table
                    conn.execute(text("DROP TABLE rsvp"))
                    conn.commit()
                    
                    # Create the new table with correct structure
                    db.create_all()
                    
                    # Reinsert the data
                    if existing_data:
                        print("📝 Restoring existing RSVP data...")
                        for row in existing_data:
                            # Convert row to dict
                            row_dict = dict(zip(columns_info, row))
                            
                            # Create new RSVP object
                            from app.models import RSVP
                            rsvp = RSVP(
                                event_id=row_dict['event_id'],
                                member_id=row_dict['member_id'],  # This can now be None
                                status=row_dict['status'],
                                acceptance_code=row_dict['acceptance_code'],
                                full_name=row_dict['full_name'],
                                email=row_dict['email'],
                                phone=row_dict['phone'],
                                course=row_dict['course'],
                                year=row_dict['year'],
                                dietary_requirements=row_dict['dietary_requirements'],
                                emergency_contact=row_dict['emergency_contact'],
                                emergency_phone=row_dict['emergency_phone'],
                                additional_notes=row_dict['additional_notes'],
                                submitted_at=row_dict['submitted_at'],
                                approved_at=row_dict['approved_at'],
                                approved_by=row_dict['approved_by']
                            )
                            db.session.add(rsvp)
                        
                        db.session.commit()
                        print(f"✅ Restored {len(existing_data)} RSVP records")
                    
                print("✅ RSVP table structure fixed successfully!")
            else:
                print("✅ RSVP table structure is already correct!")
                
        except Exception as e:
            print(f"❌ Database migration failed: {e}")
            return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting RSVP table structure fix...")
    success = fix_rsvp_table()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("✅ RSVP table now allows NULL member_id values")
        print("✅ Non-members can now RSVP to events")
    else:
        print("\n❌ Migration failed. Please check the error messages above.")
