from flask import render_template, request, flash, redirect, url_for, jsonify, current_app
from app.routes import main_bp
from app.models import News, Event, Project, Gallery, Topic, Member, Leader, Newsletter, Blog, RSVP, User, Technology
from app import db
from datetime import datetime
import urllib.parse
import urllib.request
import json

@main_bp.route('/')
def index():
    try:
        # Get latest news (limit to 3)
        latest_news = News.query.order_by(News.published_date.desc()).limit(3).all()
        
        # Get upcoming events (next 3)
        upcoming_events = Event.query.filter(
            Event.event_date >= datetime.utcnow(),
            Event.target_audience == 'everyone'
        ).order_by(Event.event_date.asc()).limit(3).all()
        
        # Get featured projects (limit to 3)
        featured_projects = Project.query.order_by(Project.created_at.desc()).limit(3).all()
    except Exception as e:
        # If database is not ready, use empty lists
        latest_news = []
        upcoming_events = []
        featured_projects = []
    
    return render_template('index.html', 
                         latest_news=latest_news,
                         upcoming_events=upcoming_events,
                         featured_projects=featured_projects)

@main_bp.route('/about')
def about():
    return render_template('about.html')

@main_bp.route('/leaders')
def leaders():
    try:
        from sqlalchemy.orm import joinedload
        leaders = Leader.query.options(joinedload(Leader.user).joinedload(User.member)).order_by(Leader.display_order.asc()).all()
    except Exception as e:
        print(f"Error loading leaders: {e}")
        leaders = []
    return render_template('leaders.html', leaders=leaders)

@main_bp.route('/alumni')
def alumni():
    try:
        page = request.args.get('page', 1, type=int)
        course_filter = request.args.get('course', '')
        year_filter = request.args.get('year', '')
        
        # Query only alumni members
        query = Member.query.join(Member.user).filter(
            Member.user.has(is_approved=True),
            Member.status == 'alumni'
        )
        
        if course_filter:
            query = query.filter(Member.course.ilike(f'%{course_filter}%'))
        if year_filter:
            query = query.filter(Member.year.ilike(f'%{year_filter}%'))
        
        alumni = query.all()
        
        # Get unique courses and years for filter dropdowns
        courses = db.session.query(Member.course).filter(Member.status == 'alumni').distinct().all()
        years = db.session.query(Member.year).filter(Member.status == 'alumni').distinct().all()
        
        # Add trophy data to each alumni member
        for alumnus in alumni:
            alumnus.trophies = alumnus.get_current_trophies()
        
        # Calculate statistics
        alumni_count = Member.query.filter(Member.status == 'alumni').count()
        companies_count = len(set([m.title for m in Member.query.filter(Member.status == 'alumni', Member.title.isnot(None)).all() if m.title]))
        countries_count = 1  # Default to 1, can be enhanced later
        current_year = datetime.now().year
        
        return render_template('alumni.html', 
                             alumni=alumni,
                             courses=[c[0] for c in courses if c[0]],
                             years=[y[0] for y in years if y[0]],
                             alumni_count=alumni_count,
                             companies_count=companies_count,
                             countries_count=countries_count,
                             current_year=current_year)
    except Exception as e:
        # Return empty results if database is not ready
        from flask import make_response
        return make_response(render_template('alumni.html', 
                                           alumni=None,
                                           courses=[],
                                           years=[],
                                           alumni_count=0,
                                           companies_count=0,
                                           countries_count=0,
                                           current_year=datetime.now().year), 200)

@main_bp.route('/members')
def members():
    try:
        approved = Member.query.join(User).filter(User.is_approved == True)
        total_members = approved.count()
        students_count = approved.filter(Member.status == 'student').count()
        alumni_count = approved.filter(Member.status == 'alumni').count()

        course_counts = db.session.query(
            Member.course.label('course'),
            db.func.count(Member.id).label('members_count')
        ).join(User).filter(
            User.is_approved == True,
            Member.course.isnot(None),
            Member.course != ''
        ).group_by(Member.course).order_by(
            db.desc('members_count'),
            Member.course.asc()
        ).all()

        return render_template(
            'members.html',
            total_members=total_members,
            students_count=students_count,
            alumni_count=alumni_count,
            course_counts=course_counts,
        )
    except Exception as e:
        # Return empty results if database is not ready
        from flask import make_response
        return make_response(render_template('members.html',
                                           total_members=0,
                                           students_count=0,
                                           alumni_count=0,
                                           course_counts=[]), 200)

@main_bp.route('/students')
def students():
    try:
        page = request.args.get('page', 1, type=int)
        course_filter = request.args.get('course', '')
        year_filter = request.args.get('year', '')
        
        # Query only student members
        query = Member.query.join(Member.user).filter(
            Member.user.has(is_approved=True),
            Member.status == 'student'
        )
        
        if course_filter:
            query = query.filter(Member.course.ilike(f'%{course_filter}%'))
        if year_filter:
            query = query.filter(Member.year.ilike(f'%{year_filter}%'))
        
        students = query.all()
        
        # Get unique courses and years for filter dropdowns
        courses = db.session.query(Member.course).filter(Member.status == 'student').distinct().all()
        years = db.session.query(Member.year).filter(Member.status == 'student').distinct().all()
        
        # Add trophy data and statistics
        for student in students:
            student.trophies = student.get_current_trophies()
        
        # Calculate current year for statistics
        current_year = datetime.now().year
        
        return render_template('students.html', 
                             students=students,
                             courses=[c[0] for c in courses if c[0]],
                             years=[y[0] for y in years if y[0]],
                             current_year=current_year)
    except Exception as e:
        # Return empty results if database is not ready
        from flask import make_response
        return make_response(render_template('students.html', 
                                           students=None,
                                           courses=[],
                                           years=[],
                                           current_year=datetime.now().year), 200)

@main_bp.route('/news')
def news():
    try:
        page = request.args.get('page', 1, type=int)
        category_filter = request.args.get('category', '')
        
        query = News.query.order_by(News.published_date.desc())
        
        if category_filter:
            query = query.filter(News.category == category_filter)
        
        news_items = query.paginate(page=page, per_page=6, error_out=False)
    except:
        news_items = None
    return render_template('news.html', news_items=news_items)

@main_bp.route('/news/<int:news_id>')
def news_detail(news_id):
    news_item = News.query.get_or_404(news_id)
    return render_template('news_detail.html', news_item=news_item)

@main_bp.route('/events')
def events():
    try:
        # Get filter parameters
        category_filter = request.args.get('category', '')
        
        query = Event.query.filter(Event.target_audience == 'everyone')
        
        # Apply category filter
        if category_filter:
            query = query.filter_by(category=category_filter)
        
        # Get all events
        all_events = query.order_by(Event.event_date.desc()).all()
        
        # Separate upcoming and past events
        now = datetime.utcnow()
        upcoming_events = [e for e in all_events if e.event_date > now]
        past_events = [e for e in all_events if e.event_date <= now]
        
        # Sort upcoming events ascending (soonest first)
        upcoming_events.sort(key=lambda x: x.event_date)
        # Sort past events descending (most recent first)
        past_events.sort(key=lambda x: x.event_date, reverse=True)
        
        # Get category counts for the category cards
        category_counts = {
            'workshop': Event.query.filter_by(category='workshop', target_audience='everyone').count(),
            'hackathon': Event.query.filter_by(category='hackathon', target_audience='everyone').count(),
            'tech_talk': Event.query.filter_by(category='tech_talk', target_audience='everyone').count(),
            'social_event': Event.query.filter_by(category='social_event', target_audience='everyone').count()
        }
        
        # Get events for calendar (all events with dates)
        calendar_events = []
        for event in all_events:
            calendar_events.append({
                'id': event.id,
                'title': event.title,
                'date': event.event_date.strftime('%Y-%m-%d'),
                'time': event.event_date.strftime('%H:%M'),
                'category': event.category,
                'location': event.location
            })
        
    except Exception as e:
        print(f"Error loading events: {e}")
        upcoming_events = []
        past_events = []
        category_counts = {'workshop': 0, 'hackathon': 0, 'tech_talk': 0, 'social_event': 0}
        calendar_events = []
    
    return render_template('events.html', 
                         upcoming_events=upcoming_events,
                         past_events=past_events,
                         category_counts=category_counts,
                         calendar_events=calendar_events,
                         current_category=category_filter)

@main_bp.route('/projects')
def projects():
    try:
        # Get filter parameter
        category_filter = request.args.get('category', '')
        
        # Get all public projects (both admin and member projects), featured first
        query = Project.query.filter_by(is_public=True)
        
        # Apply category filter based on technologies
        if category_filter:
            # Get technologies for this category from the database
            category_technologies = Technology.query.filter_by(category=category_filter, is_active=True).all()
            
            if category_technologies:
                # Create a list of technology names for this category
                tech_names = [tech.name.lower() for tech in category_technologies]
                
                # Filter projects that contain any of these technologies
                query = query.filter(
                    db.or_(*[Project.technologies.ilike(f'%{tech_name}%') for tech_name in tech_names])
                )
            else:
                # Fallback to hardcoded lists if no technologies in database
                if category_filter == 'web':
                    web_techs = ['html', 'css', 'javascript', 'react', 'vue', 'angular', 'node', 'express', 'django', 'flask', 'php', 'laravel', 'wordpress', 'bootstrap', 'tailwind']
                    query = query.filter(
                        db.or_(*[Project.technologies.ilike(f'%{tech}%') for tech in web_techs])
                    )
                elif category_filter == 'mobile':
                    mobile_techs = ['react native', 'flutter', 'swift', 'kotlin', 'android', 'ios', 'xamarin', 'ionic', 'cordova']
                    query = query.filter(
                        db.or_(*[Project.technologies.ilike(f'%{tech}%') for tech in mobile_techs])
                    )
                elif category_filter == 'ai':
                    ai_techs = ['python', 'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'opencv', 'numpy', 'pandas', 'machine learning', 'deep learning', 'neural network', 'ai', 'artificial intelligence']
                    query = query.filter(
                        db.or_(*[Project.technologies.ilike(f'%{tech}%') for tech in ai_techs])
                    )
                elif category_filter == 'iot':
                    iot_techs = ['arduino', 'raspberry pi', 'esp32', 'esp8266', 'sensors', 'mqtt', 'iot', 'internet of things', 'embedded', 'microcontroller']
                    query = query.filter(
                        db.or_(*[Project.technologies.ilike(f'%{tech}%') for tech in iot_techs])
                    )
                elif category_filter == 'data':
                    data_techs = ['python', 'r', 'sql', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'plotly', 'jupyter', 'data science', 'analytics', 'visualization', 'machine learning']
                    query = query.filter(
                        db.or_(*[Project.technologies.ilike(f'%{tech}%') for tech in data_techs])
                    )
        
        projects = query.order_by(Project.is_featured.desc(), Project.created_at.desc()).all()
    except Exception as e:
        print(f"Error loading projects: {e}")
        projects = []
    return render_template('projects.html', projects=projects, current_category=category_filter)

@main_bp.route('/gallery')
def gallery():
    try:
        gallery_items = Gallery.query.order_by(Gallery.uploaded_at.desc()).all()
    except:
        gallery_items = []
    return render_template('gallery.html', gallery_items=gallery_items)

@main_bp.route('/topics')
def topics():
    try:
        topics = Topic.query.all()
    except:
        topics = []
    return render_template('topics.html', topics=topics)

@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Handle contact form submission
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        # Here you could save to database or send email
        flash('Thank you for your message! We will get back to you soon.', 'success')
        return redirect(url_for('main.contact'))
    
    return render_template('contact.html')

@main_bp.route('/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    try:
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        if not email and not phone:
            return jsonify({'success': False, 'message': 'Please provide email or phone number'})
        
        # Check if already subscribed
        existing = Newsletter.query.filter(
            (Newsletter.email == email) | (Newsletter.phone == phone)
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Already subscribed to newsletter'})
        
        # Add new subscription
        subscription = Newsletter(email=email, phone=phone)
        db.session.add(subscription)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Successfully subscribed to newsletter!'})
    except Exception as e:
        return jsonify({'success': False, 'message': 'Database error. Please try again later.'})

# Blog Routes
@main_bp.route('/blogs')
def blogs():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    
    query = Blog.query.filter_by(is_published=True)
    
    if category:
        query = query.filter_by(category=category)
    
    blogs = query.order_by(Blog.published_date.desc()).paginate(
        page=page, per_page=6, error_out=False
    )
    
    # Get categories for filter
    categories = db.session.query(Blog.category).filter_by(is_published=True).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('blogs.html', blogs=blogs, categories=categories, current_category=category)

@main_bp.route('/blogs/<slug>')
def blog_post(slug):
    blog = Blog.query.filter_by(slug=slug, is_published=True).first_or_404()
    
    # Increment view count
    blog.views += 1
    db.session.commit()
    
    # Get related posts
    related_posts = Blog.query.filter(
        Blog.category == blog.category,
        Blog.id != blog.id,
        Blog.is_published == True
    ).order_by(Blog.published_date.desc()).limit(3).all()
    
    return render_template('blog_post.html', blog=blog, related_posts=related_posts)

def _verify_turnstile(response_token, remote_ip=None):
    secret = current_app.config.get('TURNSTILE_SECRET_KEY', '')
    if not secret or not response_token:
        return False
    try:
        payload = {
            'secret': secret,
            'response': response_token,
        }
        if remote_ip:
            payload['remoteip'] = remote_ip
        data = urllib.parse.urlencode(payload).encode('utf-8')
        req = urllib.request.Request(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data=data,
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return bool(result.get('success'))
    except Exception:
        return False


# RSVP Routes
@main_bp.route('/events/<int:event_id>/rsvp', methods=['GET', 'POST'])
def event_rsvp(event_id):
    event = Event.query.get_or_404(event_id)
    if event.target_audience != 'everyone':
        flash('This event RSVP is only available in the member panel.', 'warning')
        return redirect(url_for('main.events'))
    
    if request.method == 'POST':
        # Get form data
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        course = request.form.get('course')
        year = request.form.get('year')
        dietary_requirements = request.form.get('dietary_requirements')
        emergency_contact = request.form.get('emergency_contact')
        emergency_phone = request.form.get('emergency_phone')
        additional_notes = request.form.get('additional_notes')
        turnstile_token = (request.form.get('cf-turnstile-response') or '').strip()
        
        attendee_type = (request.form.get('attendee_type') or '').strip()
        study_field = (request.form.get('study_field') or '').strip()
        study_year = (request.form.get('study_year') or '').strip()
        non_student_role = (request.form.get('non_student_role') or '').strip()

        # Validation
        if not all([full_name, email, phone]):
            flash('Please fill in all required fields, including phone number.', 'error')
            return render_template('rsvp_form.html', event=event, turnstile_site_key=current_app.config.get('TURNSTILE_SITE_KEY', ''))

        if attendee_type not in ['student', 'non_student']:
            flash('Please select your attendance type.', 'error')
            return render_template('rsvp_form.html', event=event, turnstile_site_key=current_app.config.get('TURNSTILE_SITE_KEY', ''))

        if attendee_type == 'student':
            if not study_field or not study_year:
                flash('Please select your field of study and year.', 'error')
                return render_template('rsvp_form.html', event=event, turnstile_site_key=current_app.config.get('TURNSTILE_SITE_KEY', ''))
        else:
            if non_student_role not in ['staff', 'guest']:
                flash('Please select staff or guest.', 'error')
                return render_template('rsvp_form.html', event=event, turnstile_site_key=current_app.config.get('TURNSTILE_SITE_KEY', ''))

        if not current_app.config.get('TURNSTILE_SITE_KEY') or not current_app.config.get('TURNSTILE_SECRET_KEY'):
            flash('Cloudflare Turnstile is not configured yet. Please contact admin.', 'error')
            return render_template('rsvp_form.html', event=event, turnstile_site_key='')

        if not _verify_turnstile(turnstile_token, request.remote_addr):
            flash('Please complete the human verification and try again.', 'error')
            return render_template('rsvp_form.html', event=event, turnstile_site_key=current_app.config.get('TURNSTILE_SITE_KEY', ''))
        
        # Check if already RSVP'd
        existing_rsvp = RSVP.query.filter(
            RSVP.event_id == event_id,
            db.or_(RSVP.email == email, RSVP.phone == phone)
        ).first()
        if existing_rsvp:
            flash('You have already RSVP\'d for this event.', 'warning')
            return redirect(url_for('main.events'))
        
        # Try to link with member if exists
        member = Member.query.join(Member.user).filter(Member.user.has(email=email)).first()
        
        # Create RSVP with linked member when available.
        rsvp = RSVP(
            event_id=event_id,
            member_id=member.id if member else None,
            full_name=full_name,
            email=email,
            phone=phone,
            course=course,
            year=year,
            attendee_type=attendee_type,
            study_field=study_field if attendee_type == 'student' else None,
            study_year=study_year if attendee_type == 'student' else None,
            non_student_role=non_student_role if attendee_type == 'non_student' else None,
            dietary_requirements=dietary_requirements,
            emergency_contact=emergency_contact,
            emergency_phone=emergency_phone,
            additional_notes=additional_notes
        )
        
        db.session.add(rsvp)
        db.session.commit()
        
        flash('RSVP submitted successfully! You will receive an email/SMS once approved.', 'success')
        return redirect(url_for('main.events'))
    
    return render_template('rsvp_form.html', event=event, turnstile_site_key=current_app.config.get('TURNSTILE_SITE_KEY', ''))

## RSVP status page removed. Use flash notifications on events listing instead.

