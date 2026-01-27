"""
Migration script to fix password_hash column size in PostgreSQL
This increases the column from VARCHAR(128) to VARCHAR(256) to accommodate scrypt hashes
"""

from app import create_app, db
from sqlalchemy import text

def migrate_password_hash():
    """Alter the password_hash column to support longer scrypt hashes"""
    app = create_app()
    
    with app.app_context():
        try:
            print("Starting password_hash column migration...")
            
            # Check if we're using PostgreSQL
            db_url = app.config['SQLALCHEMY_DATABASE_URI']
            if 'postgresql' in db_url.lower():
                print("Detected PostgreSQL database")
                
                # Alter the column to increase size
                with db.engine.connect() as conn:
                    # Use ALTER TABLE to change column type
                    conn.execute(text('ALTER TABLE "user" ALTER COLUMN password_hash TYPE VARCHAR(256)'))
                    conn.commit()
                
                print("✅ Successfully updated password_hash column to VARCHAR(256)")
                print("✅ Migration completed!")
            else:
                print("⚠️  Not using PostgreSQL - migration not needed")
                print("   SQLite doesn't enforce VARCHAR length limits")
                
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            print("\nIf the column doesn't exist yet, the tables will be created")
            print("with the correct size on next app startup.")
            db.session.rollback()
            raise

if __name__ == "__main__":
    migrate_password_hash()

