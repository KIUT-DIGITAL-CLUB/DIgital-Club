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
        else:
            print("Admin user already exists.")

        # Add sample data
        add_sample_data()
        print("Database initialized with sample data (if missing).")
    except Exception as e:
        print(f"Database init error (can usually be ignored if already set up): {e}")

def add_sample_data():
    """Add sample data for testing (only if it does not already exist)."""
    # Sample topics
    topics_data = [
        {
            "name": "Python Programming",
            "description": "Learn Python from basics to advanced concepts",
            "icon": "fab fa-python",
        },
        {
            "name": "Web Development",
            "description": "HTML, CSS, JavaScript, and modern frameworks",
            "icon": "fas fa-code",
        },
        {
            "name": "Mobile Development",
            "description": "Android and iOS app development",
            "icon": "fas fa-mobile-alt",
        },
        {
            "name": "Data Science",
            "description": "Data analysis, machine learning, and AI",
            "icon": "fas fa-chart-line",
        },
        {
            "name": "Cybersecurity",
            "description": "Ethical hacking and security practices",
            "icon": "fas fa-shield-alt",
        },
        {
            "name": "Cloud Computing",
            "description": "AWS, Azure, and cloud technologies",
            "icon": "fas fa-cloud",
        },
    ]

    for topic_data in topics_data:
        if not Topic.query.filter_by(name=topic_data["name"]).first():
            topic = Topic(**topic_data)
            db.session.add(topic)

    # Sample news
    news_data = [
        {
            "title": "Digital Club Hackathon 2024 Registration Open!",
            "content": "Join us for the biggest hackathon of the year! Build innovative solutions and compete for amazing prizes.",
            "category": "hackathon",
        },
        {
            "title": "New Python Workshop Series Starting",
            "content": "Learn Python programming from scratch in our comprehensive workshop series.",
            "category": "workshop",
        },
        {
            "title": "Club Members Win National Coding Competition",
            "content": "Congratulations to our team for securing first place in the national coding competition!",
            "category": "achievement",
        },
    ]

    # admin_user = User.query.filter_by(role="admin").first()
    # for news_item_data in news_data:
    #     if not News.query.filter_by(title=news_item_data["title"]).first() and admin_user:
    #         news_item = News(author_id=admin_user.id, **news_item_data)
    #         db.session.add(news_item)

    # Sample events
    from datetime import datetime, timedelta, timezone

    events_data = [
        {
            "title": "Python Workshop",
            "description": "Introduction to Python programming",
            "event_date": datetime.now(timezone.utc) + timedelta(days=7),
            "location": "Computer Lab 1",
        },
        {
            "title": "Hackathon Kickoff",
            "description": "Digital Club Hackathon 2024 kickoff event",
            "event_date": datetime.now(timezone.utc) + timedelta(days=14),
            "location": "Main Auditorium",
        },
    ]

    # for event_data in events_data:
    #     if not Event.query.filter_by(title=event_data["title"]).first():
    #         event = Event(**event_data)
    #         db.session.add(event)

    # Sample blog posts
    blog_data = [
        {
            "title": "Getting Started with Python Programming",
            "slug": "getting-started-with-python-programming",
            "content": '''
            <h2>Why Learn Python?</h2>
            <p>Python is one of the most popular programming languages today, known for its simplicity and versatility. Whether you're interested in web development, data science, artificial intelligence, or automation, Python has something to offer.</p>
            
            <h3>Key Features of Python:</h3>
            <ul>
                <li><strong>Easy to Learn:</strong> Python's syntax is clean and readable</li>
                <li><strong>Versatile:</strong> Used in web development, data science, AI, and more</li>
                <li><strong>Large Community:</strong> Extensive libraries and frameworks</li>
                <li><strong>Cross-Platform:</strong> Runs on Windows, Mac, and Linux</li>
            </ul>
            
            <h3>Getting Started</h3>
            <p>To begin your Python journey, you'll need to install Python on your computer. Visit <a href="https://python.org">python.org</a> to download the latest version.</p>
            
            <h3>Your First Python Program</h3>
            <pre><code>print("Hello, Digital Club!")</code></pre>
            
            <p>This simple program demonstrates Python's straightforward syntax. As you progress, you'll learn about variables, functions, classes, and more advanced concepts.</p>
            ''',
            "excerpt": "Learn the basics of Python programming and why it's the perfect language for beginners.",
            "category": "tutorial",
            "tags": "python, programming, tutorial, beginner",
            "is_published": True,
            "published_date": datetime.now(timezone.utc) - timedelta(days=5),
        },
        {
            "title": "Digital Club Hackathon 2024: A Complete Guide",
            "slug": "digital-club-hackathon-2024-complete-guide",
            "content": '''
            <h2>What is the Digital Club Hackathon?</h2>
            <p>The Digital Club Hackathon is our annual 48-hour coding competition where students come together to build innovative solutions to real-world problems.</p>
            
            <h3>Event Details</h3>
            <ul>
                <li><strong>Date:</strong> March 15-17, 2024</li>
                <li><strong>Duration:</strong> 48 hours</li>
                <li><strong>Location:</strong> Computer Science Building</li>
                <li><strong>Registration Fee:</strong> Free for all KIUT students</li>
            </ul>
            
            <h3>How to Prepare</h3>
            <p>Preparation is key to hackathon success. Here are some tips:</p>
            <ol>
                <li>Form a diverse team with different skill sets</li>
                <li>Practice coding challenges and algorithms</li>
                <li>Learn about APIs and databases</li>
                <li>Prepare your development environment</li>
            </ol>
            
            <h3>Prizes</h3>
            <p>This year's hackathon features amazing prizes including:</p>
            <ul>
                <li>1st Place: Tsh 1000 + Internship opportunities</li>
                <li>2nd Place: Tsh 500 + Mentorship program</li>
                <li>3rd Place: Tsh 250 + Tech gadgets</li>
            </ul>
            ''',
            "excerpt": "Everything you need to know about participating in our annual hackathon event.",
            "category": "event",
            "tags": "hackathon, competition, programming, event",
            "is_published": True,
            "published_date": datetime.now(timezone.utc) - timedelta(days=3),
        },
        {
            "title": "The Future of Web Development: Trends to Watch",
            "slug": "future-of-web-development-trends-2024",
            "content": '''
            <h2>Emerging Technologies in Web Development</h2>
            <p>Web development is constantly evolving, and 2024 brings exciting new trends that every developer should be aware of.</p>
            
            <h3>1. Artificial Intelligence Integration</h3>
            <p>AI is becoming increasingly integrated into web applications, from chatbots to personalized user experiences. Tools like ChatGPT API and machine learning libraries are making AI more accessible to web developers.</p>
            
            <h3>2. Progressive Web Apps (PWAs)</h3>
            <p>PWAs continue to gain traction, offering native app-like experiences in the browser. They provide offline functionality, push notifications, and app-like performance.</p>
            
            <h3>3. WebAssembly (WASM)</h3>
            <p>WebAssembly allows high-performance code to run in browsers, enabling complex applications like games and video editors to work seamlessly on the web.</p>
            
            <h3>4. Edge Computing</h3>
            <p>With edge computing, processing happens closer to users, reducing latency and improving performance. This is particularly important for real-time applications.</p>
            
            <h3>5. Sustainable Web Development</h3>
            <p>There's a growing focus on creating energy-efficient websites and applications, considering the environmental impact of digital technologies.</p>
            
            <h3>Conclusion</h3>
            <p>Staying updated with these trends is crucial for any web developer. The industry moves fast, and continuous learning is the key to success.</p>
            ''',
            "excerpt": "Explore the latest trends and technologies shaping the future of web development in 2024.",
            "category": "tech",
            "tags": "web development, trends, technology, future",
            "is_published": True,
            "published_date": datetime.now(timezone.utc) - timedelta(days=1),
        },
    ]

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
