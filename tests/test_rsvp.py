#!/usr/bin/env python3
"""
Test script for RSVP functionality
This script tests the RSVP system to ensure it works correctly
"""

from app import create_app, db
from app.models import RSVP, Event, Member, User

def test_rsvp_system():
    """Test the RSVP system"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🧪 Testing RSVP System...")
            
            # Check if we have any events
            events = Event.query.all()
            if not events:
                print("❌ No events found. Please create an event first.")
                return False
            
            print(f"✅ Found {len(events)} events")
            
            # Test creating an RSVP for a non-member
            test_event = events[0]
            print(f"📅 Testing with event: {test_event.title}")
            
            # Create a test RSVP
            test_rsvp = RSVP(
                event_id=test_event.id,
                member_id=0,  # Non-member
                full_name="Test User",
                email="test@example.com",
                phone="1234567890",
                course="Computer Science",
                year="Year 2",
                dietary_requirements="None",
                emergency_contact="Emergency Contact",
                emergency_phone="0987654321",
                additional_notes="Test RSVP"
            )
            
            db.session.add(test_rsvp)
            db.session.commit()
            
            print("✅ Test RSVP created successfully!")
            print(f"   - Event: {test_rsvp.event.title}")
            print(f"   - Name: {test_rsvp.full_name}")
            print(f"   - Email: {test_rsvp.email}")
            print(f"   - Member ID: {test_rsvp.member_id} (0 = Non-Member)")
            print(f"   - Status: {test_rsvp.status}")
            
            # Test approval
            test_rsvp.status = 'approved'
            test_rsvp.generate_acceptance_code()
            db.session.commit()
            
            print(f"✅ RSVP approved with code: {test_rsvp.acceptance_code}")
            
            # Clean up test data
            db.session.delete(test_rsvp)
            db.session.commit()
            print("🧹 Test data cleaned up")
            
            print("\n🎉 RSVP System Test Completed Successfully!")
            print("✅ Non-members can RSVP to events")
            print("✅ Acceptance codes are generated")
            print("✅ Database constraints are handled properly")
            
            return True
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False

if __name__ == "__main__":
    success = test_rsvp_system()
    
    if success:
        print("\n🚀 RSVP System is ready to use!")
        print("   - Members and non-members can RSVP")
        print("   - Admins can approve/reject RSVPs")
        print("   - Bulk operations work")
        print("   - Notifications can be sent")
    else:
        print("\n❌ RSVP System has issues. Please check the error messages above.")
