"""
Migration script for Rewards and Membership Payment System
Creates new tables and adds new columns to existing tables
"""

from app import create_app, db
from app.models import (
    RewardTransaction, Trophy, MemberTrophy, MembershipPayment, 
    SystemSettings, Event, RSVP
)
from datetime import datetime

def migrate_database():
    """Run the migration"""
    app = create_app()
    
    with app.app_context():
        print("Starting migration for Rewards & Membership System...")
        
        # Create all new tables
        print("\n1. Creating new tables...")
        db.create_all()
        print("   ✓ Tables created successfully")
        
        # Add new columns to existing tables (if not already present)
        print("\n2. Updating existing tables...")
        try:
            # Check if Event table has new columns, add if not
            with db.engine.connect() as conn:
                # For Event: allows_check_in, check_in_points
                try:
                    conn.execute(db.text("ALTER TABLE event ADD COLUMN allows_check_in BOOLEAN DEFAULT TRUE"))
                    print("   ✓ Added 'allows_check_in' to Event table")
                except Exception as e:
                    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                        print("   - 'allows_check_in' already exists in Event table")
                    else:
                        print(f"   ! Error adding 'allows_check_in': {e}")
                
                try:
                    conn.execute(db.text("ALTER TABLE event ADD COLUMN check_in_points INTEGER DEFAULT 0"))
                    print("   ✓ Added 'check_in_points' to Event table")
                except Exception as e:
                    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                        print("   - 'check_in_points' already exists in Event table")
                    else:
                        print(f"   ! Error adding 'check_in_points': {e}")
                
                # For RSVP: checked_in, checked_in_at, checked_in_by
                try:
                    conn.execute(db.text("ALTER TABLE rsvp ADD COLUMN checked_in BOOLEAN DEFAULT FALSE"))
                    print("   ✓ Added 'checked_in' to RSVP table")
                except Exception as e:
                    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                        print("   - 'checked_in' already exists in RSVP table")
                    else:
                        print(f"   ! Error adding 'checked_in': {e}")
                
                try:
                    conn.execute(db.text("ALTER TABLE rsvp ADD COLUMN checked_in_at DATETIME"))
                    print("   ✓ Added 'checked_in_at' to RSVP table")
                except Exception as e:
                    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                        print("   - 'checked_in_at' already exists in RSVP table")
                    else:
                        print(f"   ! Error adding 'checked_in_at': {e}")
                
                try:
                    conn.execute(db.text("ALTER TABLE rsvp ADD COLUMN checked_in_by INTEGER REFERENCES user(id)"))
                    print("   ✓ Added 'checked_in_by' to RSVP table")
                except Exception as e:
                    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                        print("   - 'checked_in_by' already exists in RSVP table")
                    else:
                        print(f"   ! Error adding 'checked_in_by': {e}")
                
                conn.commit()
        
        except Exception as e:
            print(f"   ! Error updating tables: {e}")
        
        # Insert default trophies
        print("\n3. Creating default trophies...")
        trophies_data = [
            {
                'name': 'Alien Sticker 👽',
                'description': 'Earned for reaching 700 points. Welcome to the club!',
                'points_required': 700,
                'icon': 'fa-solid fa-user-astronaut',
                'display_order': 1
            },
            {
                'name': 'Tech Mask 🎭',
                'description': 'Earned for reaching 1,500 points. You\'re getting serious!',
                'points_required': 1500,
                'icon': 'fa-solid fa-mask',
                'display_order': 2
            },
            {
                'name': 'Bronze Badge 🥉',
                'description': 'Earned for reaching 2,500 points. Bronze tier achieved!',
                'points_required': 2500,
                'icon': 'fa-solid fa-medal',
                'display_order': 3
            },
            {
                'name': 'Silver Shield 🥈',
                'description': 'Earned for reaching 4,000 points. Silver tier unlocked!',
                'points_required': 4000,
                'icon': 'fa-solid fa-shield',
                'display_order': 4
            },
            {
                'name': 'Gold Crown 👑',
                'description': 'Earned for reaching 5,500 points. Royalty status!',
                'points_required': 5500,
                'icon': 'fa-solid fa-crown',
                'display_order': 5
            },
            {
                'name': 'Platinum Trophy 🏆',
                'description': 'Earned for reaching 7,500 points. Elite member!',
                'points_required': 7500,
                'icon': 'fa-solid fa-trophy',
                'display_order': 6
            },
            {
                'name': 'Legend Status ⭐',
                'description': 'Earned for reaching 10,000 points. You are a Digital Club Legend!',
                'points_required': 10000,
                'icon': 'fa-solid fa-star',
                'display_order': 7
            }
        ]
        
        for trophy_data in trophies_data:
            # Check if trophy already exists
            existing = Trophy.query.filter_by(name=trophy_data['name']).first()
            if not existing:
                trophy = Trophy(**trophy_data)
                db.session.add(trophy)
                print(f"   ✓ Created trophy: {trophy_data['name']}")
            else:
                print(f"   - Trophy already exists: {trophy_data['name']}")
        
        db.session.commit()
        
        # Create default system settings
        print("\n4. Creating default system settings...")
        settings_data = [
            {
                'key': 'membership_fee',
                'value': '50.00',
                'description': 'Default membership fee amount (in local currency)'
            },
            {
                'key': 'membership_duration_months',
                'value': '12',
                'description': 'Default membership duration in months'
            },
            {
                'key': 'default_event_points',
                'value': '100',
                'description': 'Default points awarded for event attendance'
            }
        ]
        
        for setting_data in settings_data:
            existing = SystemSettings.query.filter_by(setting_key=setting_data['key']).first()
            if not existing:
                setting = SystemSettings(
                    setting_key=setting_data['key'],
                    setting_value=setting_data['value'],
                    description=setting_data['description']
                )
                db.session.add(setting)
                print(f"   ✓ Created setting: {setting_data['key']} = {setting_data['value']}")
            else:
                print(f"   - Setting already exists: {setting_data['key']}")
        
        db.session.commit()
        
        print("\n" + "="*60)
        print("✓ Migration completed successfully!")
        print("="*60)
        print("\nNew features available:")
        print("  • Reward points system with 7 trophy levels")
        print("  • Membership payment tracking")
        print("  • Event check-in and attendance tracking")
        print("  • Admin ID scanner for member verification")
        print("\nNext steps:")
        print("  1. Run the Flask application")
        print("  2. Login as admin")
        print("  3. Configure membership fee in Admin > Settings")
        print("  4. Start awarding points and tracking payments!")
        print("="*60)


if __name__ == '__main__':
    migrate_database()

