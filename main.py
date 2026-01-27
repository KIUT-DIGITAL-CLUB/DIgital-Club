from app import create_app, db
from app.models import User, Topic, News, Event, Blog
import os

app = create_app()


def init_db():
    """Initialize the database with an admin account and sample data (idempotent)."""
    try:
        # Create admin user if it doesn't exist
        admin_user = User.query.filter_by(email="admin@digitalclub.kiut.ac.tz").first()
        if not admin_user:
            admin_user = User(
                email="admin@digitalclub.kiut.ac.tz",
                role="admin",
                is_approved=True,
                is_super_admin=True,
            )
            admin_user.set_password("admin123")
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created: admin@digitalclub.kiut.ac.tz / admin123")
            # ⚠️ WARNING:
            # Do NOT use these credentials in production.
            # As soon as the system goes live, these credentials should be reset.
            # These credentials are for the SUPER ADMIN account (development/testing only).

        else:
            print("Admin user already exists.")

        # Add sample data
        # add_sample_data()
        print("Database initialized with sample data (if missing).")
    except Exception as e:
        print(f"Database init error (can usually be ignored if already set up): {e}")

# def add_sample_data():
#     """Add sample data for testing (only if it does not already exist)."""
#     # Sample topics
#     topics_data = [
#         {
#             "name": "Python Programming",
#             "description": "Learn Python from basics to advanced concepts",
#             "icon": "fab fa-python",
#         },
#         {
#             "name": "Web Development",
#             "description": "HTML, CSS, JavaScript, and modern frameworks",
#             "icon": "fas fa-code",
#         },
#         {
#             "name": "Mobile Development",
#             "description": "Android and iOS app development",
#             "icon": "fas fa-mobile-alt",
#         },
#         {
#             "name": "Data Science",
#             "description": "Data analysis, machine learning, and AI",
#             "icon": "fas fa-chart-line",
#         },
#         {
#             "name": "Cybersecurity",
#             "description": "Ethical hacking and security practices",
#             "icon": "fas fa-shield-alt",
#         },
#         {
#             "name": "Cloud Computing",
#             "description": "AWS, Azure, and cloud technologies",
#             "icon": "fas fa-cloud",
#         },
#     ]

#     for topic_data in topics_data:
#         if not Topic.query.filter_by(name=topic_data["name"]).first():
#             topic = Topic(**topic_data)
#             db.session.add(topic)

#     # Sample news
#     news_data = [
#         {
#             "title": "Digital Club Hackathon 2024 Registration Open!",
#             "content": "Join us for the biggest hackathon of the year! Build innovative solutions and compete for amazing prizes.",
#             "category": "hackathon",
#         },
#         {
#             "title": "New Python Workshop Series Starting",
#             "content": "Learn Python programming from scratch in our comprehensive workshop series.",
#             "category": "workshop",
#         },
#         {
#             "title": "Club Members Win National Coding Competition",
#             "content": "Congratulations to our team for securing first place in the national coding competition!",
#             "category": "achievement",
#         },
#     ]

    # admin_user = User.query.filter_by(role="admin").first()
    # for news_item_data in news_data:
    #     if not News.query.filter_by(title=news_item_data["title"]).first() and admin_user:
    #         news_item = News(author_id=admin_user.id, **news_item_data)
    #         db.session.add(news_item)

    # # Sample events
    # from datetime import datetime, timedelta, timezone

    # events_data = [
    #     {
    #         "title": "Python Workshop",
    #         "description": "Introduction to Python programming",
    #         "event_date": datetime.now(timezone.utc) + timedelta(days=7),
    #         "location": "Computer Lab 1",
    #     },
    #     {
    #         "title": "Hackathon Kickoff",
    #         "description": "Digital Club Hackathon 2024 kickoff event",
    #         "event_date": datetime.now(timezone.utc) + timedelta(days=14),
    #         "location": "Main Auditorium",
    #     },
    # ]

    # for event_data in events_data:
    #     if not Event.query.filter_by(title=event_data["title"]).first():
    #         event = Event(**event_data)
    #         db.session.add(event)

    # Sample blog posts
    blog_data = []

    # admin_user = User.query.filter_by(role="admin").first()
    # for blog_item_data in blog_data:
    #     if not Blog.query.filter_by(title=blog_item_data["title"]).first() and admin_user:
    #         blog_item = Blog(author_id=admin_user.id, **blog_item_data)
    #         db.session.add(blog_item)

    # db.session.commit()


# Ensure DB and admin user are initialized whenever the app starts (e.g. under Gunicorn)
with app.app_context():
    init_db()


if __name__ == "__main__":
    # When running directly with `python main.py`, also ensure DB is initialized
    with app.app_context():
        init_db()
    # Bind to 0.0.0.0 to accept connections from outside the container
    port = int(os.environ.get('PORT', 5051))
    app.run(host='0.0.0.0', port=port, debug=True)
