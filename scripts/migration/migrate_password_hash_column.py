"""
Migration script to alter password_hash column from varchar(128) to varchar(256)
Run this script to fix the database schema mismatch.
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

def migrate_password_hash():
    """Alter password_hash column to support longer scrypt hashes"""
    with app.app_context():
        try:
            # Check if using PostgreSQL
            if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']:
                # PostgreSQL: Use ALTER TABLE
                with db.engine.connect() as conn:
                    # Check current column type
                    result = conn.execute(text("""
                        SELECT character_maximum_length 
                        FROM information_schema.columns 
                        WHERE table_name = 'user' 
                        AND column_name = 'password_hash'
                    """))
                    row = result.fetchone()
                    
                    if row and row[0] == 128:
                        print("Altering password_hash column from varchar(128) to varchar(256)...")
                        conn.execute(text("ALTER TABLE \"user\" ALTER COLUMN password_hash TYPE VARCHAR(256)"))
                        conn.commit()
                        print("✓ Successfully altered password_hash column to VARCHAR(256)")
                    elif row and row[0] == 256:
                        print("✓ password_hash column is already VARCHAR(256)")
                    else:
                        print(f"⚠ Column type is {row[0] if row else 'unknown'}, skipping migration")
            else:
                # SQLite: Recreate table (SQLite doesn't support ALTER COLUMN)
                print("SQLite detected. Recreating user table with updated schema...")
                # SQLite requires recreating the table
                with db.engine.connect() as conn:
                    # Create new table with correct schema
                    conn.execute(text("""
                        CREATE TABLE user_new (
                            id INTEGER PRIMARY KEY,
                            email VARCHAR(120) UNIQUE NOT NULL,
                            password_hash VARCHAR(256),
                            role VARCHAR(20) DEFAULT 'student',
                            is_approved BOOLEAN DEFAULT 0,
                            is_super_admin BOOLEAN DEFAULT 0,
                            created_at DATETIME
                        )
                    """))
                    
                    # Copy data
                    conn.execute(text("""
                        INSERT INTO user_new (id, email, password_hash, role, is_approved, is_super_admin, created_at)
                        SELECT id, email, password_hash, role, is_approved, is_super_admin, created_at
                        FROM user
                    """))
                    
                    # Drop old table
                    conn.execute(text("DROP TABLE user"))
                    
                    # Rename new table
                    conn.execute(text("ALTER TABLE user_new RENAME TO user"))
                    conn.commit()
                    print("✓ Successfully recreated user table with VARCHAR(256) password_hash")
        except Exception as e:
            print(f"Error during migration: {e}")
            print("This might be expected if the column is already the correct size.")
            db.session.rollback()

if __name__ == "__main__":
    migrate_password_hash()

