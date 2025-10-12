"""
Migration script to add digital ID fields and generate IDs for existing members
Run this script to update the database with the new digital ID fields
"""

from app import create_app, db
from app.models import Member
from datetime import datetime
from sqlalchemy import text

app = create_app()

def migrate_digital_ids():
    """Add digital ID fields and generate IDs for existing members"""
    with app.app_context():
        print("Starting digital ID migration...")
        
        # Check if columns already exist
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('member')]
        
        # Add new columns if they don't exist (SQLite)
        if 'member_id_number' not in columns:
            print("Adding member_id_number column...")
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE member ADD COLUMN member_id_number VARCHAR(20)'))
                conn.commit()
            print("[OK] Added member_id_number column")
        else:
            print("[OK] member_id_number column already exists")
        
        if 'digital_id_path' not in columns:
            print("Adding digital_id_path column...")
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE member ADD COLUMN digital_id_path VARCHAR(200)'))
                conn.commit()
            print("[OK] Added digital_id_path column")
        else:
            print("[OK] digital_id_path column already exists")
        
        if 'created_at' not in columns:
            print("Adding created_at column...")
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE member ADD COLUMN created_at DATETIME'))
                # Set default value for existing rows
                conn.execute(text("UPDATE member SET created_at = datetime('now') WHERE created_at IS NULL"))
                conn.commit()
            print("[OK] Added created_at column")
        else:
            print("[OK] created_at column already exists")
        
        # Generate member IDs for existing members who don't have one
        members_without_ids = Member.query.filter(
            (Member.member_id_number == None) | (Member.member_id_number == '')
        ).all()
        
        if not members_without_ids:
            print("[OK] All members already have ID numbers")
            print("\nMigration completed successfully!")
            print("Note: Digital ID cards will be generated automatically when members log in.")
            return
        
        print(f"Found {len(members_without_ids)} members without ID numbers")
        
        for member in members_without_ids:
            # Generate member ID
            member.generate_member_id()
            print(f"  - Generated ID {member.member_id_number} for {member.full_name}")
        
        # Commit all changes
        db.session.commit()
        print(f"[OK] Successfully generated {len(members_without_ids)} member IDs")
        
        print("\nMigration completed successfully!")
        print("Note: Digital ID cards will be generated automatically when members log in.")

if __name__ == "__main__":
    migrate_digital_ids()

