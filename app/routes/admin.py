from flask import render_template, request, flash, redirect, url_for, jsonify, current_app, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.routes import admin_bp
from app.models import (
    User, Member, Leader, News, Event, Project, Gallery, Topic, Newsletter, 
    Blog, RSVP, Technology, RewardTransaction, Trophy, MemberTrophy, 
    MembershipPayment, SystemSettings, FinancialPeriod, FinancialCategory, 
    FinancialTransaction, Competition, CompetitionJudge, CompetitionCriteria,
    CompetitionSubmission, CompetitionScore, CompetitionReward,
    CompetitionSponsor, CompetitionSponsorLink, CompetitionWinner, CompetitionGuard,
    CompetitionEnrollment, SessionWeek, SessionSchedule, SessionReport, Team, TeamMember,
    DailyActiveUser
)
from app import db
from app.utils import get_notification_service
from app.pdf_generator import generate_member_ids_pdf
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None
import os
import json
import csv
import io

def admin_required(f):
    """Decorator to require admin role"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    # Get statistics
    total_members = Member.query.join(User).filter(User.is_approved == True).count()
    pending_approvals = User.query.filter_by(role='student', is_approved=False).count()
    upcoming_events = Event.query.filter(Event.event_date >= datetime.utcnow()).count()
    newsletter_subscribers = Newsletter.query.filter_by(is_active=True).count()
    try:
        today_local = datetime.utcnow().date()
        daily_active_users = DailyActiveUser.query.filter_by(activity_date=today_local).count()
    except Exception:
        daily_active_users = 0
    recent_active_users = DailyActiveUser.query.order_by(DailyActiveUser.last_seen_at.desc()).limit(10).all()
    
    # Get financial statistics
    current_period = FinancialPeriod.query.filter_by(status='open').first()
    current_revenue = current_period.get_total_revenue() if current_period else 0
    current_expenses = current_period.get_total_expenses() if current_period else 0
    current_balance = current_revenue - current_expenses
    
    # Get recent activity
    recent_news = News.query.order_by(News.published_date.desc()).limit(5).all()
    pending_users = User.query.filter_by(role='student', is_approved=False).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_members=total_members,
                         pending_approvals=pending_approvals,
                         upcoming_events=upcoming_events,
                         newsletter_subscribers=newsletter_subscribers,
                         daily_active_users=daily_active_users,
                         recent_active_users=recent_active_users,
                         recent_news=recent_news,
                         pending_users=pending_users,
                         current_period=current_period,
                         current_revenue=current_revenue,
                         current_expenses=current_expenses,
                         current_balance=current_balance)

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    pending_users = User.query.filter_by(role='student', is_approved=False).all()
    return render_template('admin/users.html', pending_users=pending_users)

@admin_bp.route('/approve-user/<int:user_id>')
@login_required
@admin_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()

    try:
        notification_service = get_notification_service()
        notification_service.send_user_approval_email(user)
    except Exception as exc:
        current_app.logger.error(f"Failed to send approval email for user {user.email}: {exc}")
    
    flash(f'User {user.email} has been approved.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/reject-user/<int:user_id>')
@login_required
@admin_required
def reject_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.email} has been rejected and removed.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/news')
@login_required
@admin_required
def news():
    news_items = News.query.order_by(News.published_date.desc()).all()
    return render_template('admin/news.html', news_items=news_items)

@admin_bp.route('/news/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_news():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        
        news_item = News(
            title=title,
            content=content,
            category=category,
            author_id=current_user.id
        )
        db.session.add(news_item)
        db.session.commit()
        
        flash('News article added successfully.', 'success')
        return redirect(url_for('admin.news'))
    
    return render_template('admin/add_news.html')

@admin_bp.route('/news/edit/<int:news_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_news(news_id):
    news_item = News.query.get_or_404(news_id)
    
    if request.method == 'POST':
        news_item.title = request.form.get('title')
        news_item.content = request.form.get('content')
        news_item.category = request.form.get('category')
        db.session.commit()
        
        flash('News article updated successfully.', 'success')
        return redirect(url_for('admin.news'))
    
    return render_template('admin/edit_news.html', news_item=news_item)

@admin_bp.route('/news/delete/<int:news_id>')
@login_required
@admin_required
def delete_news(news_id):
    news_item = News.query.get_or_404(news_id)
    db.session.delete(news_item)
    db.session.commit()
    
    flash('News article deleted successfully.', 'success')
    return redirect(url_for('admin.news'))

@admin_bp.route('/events')
@login_required
@admin_required
def events():
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    category_filter = request.args.get('category', '')
    
    query = Event.query
    
    # Apply category filter
    if category_filter:
        query = query.filter_by(category=category_filter)
    
    # Get all events and group them
    all_events = query.order_by(Event.event_date.desc()).all()
    
    now = datetime.utcnow()
    upcoming_events = [e for e in all_events if e.event_date > now]
    past_events = [e for e in all_events if e.event_date <= now]
    
    # Filter based on status
    if status_filter == 'upcoming':
        events = upcoming_events
    elif status_filter == 'past':
        events = past_events
    else:
        events = all_events
    
    return render_template('admin/events.html', 
                         events=events,
                         upcoming_count=len(upcoming_events),
                         past_count=len(past_events),
                         current_status=status_filter,
                         current_category=category_filter)

@admin_bp.route('/events/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_event():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        event_date = datetime.strptime(request.form.get('event_date'), '%Y-%m-%dT%H:%M')
        location = request.form.get('location')
        category = request.form.get('category', 'workshop')
        max_attendees = request.form.get('max_attendees', type=int)
        target_audience = request.form.get('target_audience', 'everyone')
        
        # Handle image upload
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                # Create uploads directory if it doesn't exist
                upload_folder = os.path.join(current_app.static_folder, 'uploads', 'events')
                os.makedirs(upload_folder, exist_ok=True)
                
                # Secure the filename and save
                filename = secure_filename(file.filename)
                # Add timestamp to make filename unique
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                image = f'uploads/events/{filename}'
        
        event = Event(
            title=title,
            description=description,
            event_date=event_date,
            location=location,
            category=category,
            image=image,
            max_attendees=max_attendees,
            target_audience=target_audience
        )
        db.session.add(event)
        db.session.commit()
        
        flash('Event added successfully.', 'success')
        return redirect(url_for('admin.events'))
    
    return render_template('admin/add_event.html')

@admin_bp.route('/projects')
@login_required
@admin_required
def projects():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('admin/projects.html', projects=projects)

@admin_bp.route('/projects/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_project():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        github_link = request.form.get('github_link')
        demo_link = request.form.get('demo_link')
        technologies = request.form.get('technologies')
        # Handle multi-select team members
        selected_members = request.form.getlist('team_members')
        team_members = ', '.join(selected_members) if selected_members else ''
        
        project = Project(
            title=title,
            description=description,
            image=request.form.get('image'),
            github_link=github_link,
            demo_link=demo_link,
            technologies=technologies,
            team_members=team_members,
            is_admin_project=True,
            is_public=True,
            is_featured='is_featured' in request.form
        )
        db.session.add(project)
        db.session.commit()
        
        flash('Project added successfully.', 'success')
        return redirect(url_for('admin.projects'))
    
    # Get all approved members for the dropdown
    members = Member.query.join(User).filter(User.is_approved == True).order_by(Member.full_name.asc()).all()
    
    # Get all active technologies for the dropdown
    technologies = Technology.query.filter_by(is_active=True).order_by(Technology.category.asc(), Technology.name.asc()).all()
    
    return render_template('admin/add_project.html', members=members, technologies=technologies)

@admin_bp.route('/gallery')
@login_required
@admin_required
def gallery():
    gallery_items = Gallery.query.order_by(Gallery.uploaded_at.desc()).all()
    return render_template('admin/gallery.html', gallery_items=gallery_items)

@admin_bp.route('/gallery/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_gallery_item():
    if request.method == 'POST':
        item_type = request.form.get('type')
        url = request.form.get('url')
        caption = request.form.get('caption')
        
        gallery_item = Gallery(
            type=item_type,
            url=url,
            caption=caption
        )
        db.session.add(gallery_item)
        db.session.commit()
        
        flash('Gallery item added successfully.', 'success')
        return redirect(url_for('admin.gallery'))
    
    return render_template('admin/add_gallery_item.html')

@admin_bp.route('/newsletter')
@login_required
@admin_required
def newsletter():
    # Get both active and inactive subscribers
    active_subscribers = Newsletter.query.filter_by(is_active=True).order_by(Newsletter.subscribed_at.desc()).all()
    inactive_subscribers = Newsletter.query.filter_by(is_active=False).order_by(Newsletter.subscribed_at.desc()).all()
    
    return render_template('admin/newsletter.html', 
                         active_subscribers=active_subscribers,
                         inactive_subscribers=inactive_subscribers)

@admin_bp.route('/newsletter/test')
@login_required
@admin_required
def test_newsletter():
    return "Newsletter admin routes are working!"

@admin_bp.route('/newsletter/export-csv')
@login_required
@admin_required
def export_newsletter_csv():
    try:
        from flask import Response
        import csv
        import io
        from datetime import datetime
        
        # Check if we should include inactive subscribers
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        # Get subscribers based on filter
        if include_inactive:
            subscribers = Newsletter.query.order_by(Newsletter.subscribed_at.desc()).all()
            filename_suffix = 'all_subscribers'
        else:
            subscribers = Newsletter.query.filter_by(is_active=True).order_by(Newsletter.subscribed_at.desc()).all()
            filename_suffix = 'active_subscribers'
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Email', 'Phone', 'Subscription Date', 'Subscription Time', 'Status', 'Days Since Subscription'])
        
        # Write data
        for subscriber in subscribers:
            days_since = (datetime.utcnow() - subscriber.subscribed_at).days
            writer.writerow([
                subscriber.email or '',
                subscriber.phone or '',
                subscriber.subscribed_at.strftime('%Y-%m-%d'),
                subscriber.subscribed_at.strftime('%H:%M:%S'),
                'Active' if subscriber.is_active else 'Inactive',
                days_since
            ])
        
        # Prepare response
        output.seek(0)
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=newsletter_{filename_suffix}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )
        
        return response
        
    except Exception as e:
        flash(f'Error exporting CSV: {str(e)}', 'error')
        return redirect(url_for('admin.newsletter'))

@admin_bp.route('/newsletter/toggle-status/<int:subscriber_id>')
@login_required
@admin_required
def toggle_newsletter_status(subscriber_id):
    subscriber = Newsletter.query.get_or_404(subscriber_id)
    subscriber.is_active = not subscriber.is_active
    db.session.commit()
    
    status = 'activated' if subscriber.is_active else 'deactivated'
    flash(f'Subscriber {status} successfully.', 'success')
    return redirect(url_for('admin.newsletter'))

# Missing routes for edit/delete operations
@admin_bp.route('/events/edit/<int:event_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        event.title = request.form.get('title')
        event.description = request.form.get('description')
        event.event_date = datetime.strptime(request.form.get('event_date'), '%Y-%m-%dT%H:%M')
        event.location = request.form.get('location')
        event.category = request.form.get('category', 'workshop')
        event.max_attendees = request.form.get('max_attendees', type=int)
        event.target_audience = request.form.get('target_audience', 'everyone')
        
        # Handle image removal
        if 'remove_image' in request.form:
            if event.image:
                # Delete old image file
                old_image_path = os.path.join(current_app.static_folder, event.image)
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except:
                        pass  # If deletion fails, continue anyway
                event.image = None
        
        # Handle new image upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                # Delete old image if exists
                if event.image:
                    old_image_path = os.path.join(current_app.static_folder, event.image)
                    if os.path.exists(old_image_path):
                        try:
                            os.remove(old_image_path)
                        except:
                            pass
                
                # Create uploads directory if it doesn't exist
                upload_folder = os.path.join(current_app.static_folder, 'uploads', 'events')
                os.makedirs(upload_folder, exist_ok=True)
                
                # Secure the filename and save
                filename = secure_filename(file.filename)
                # Add timestamp to make filename unique
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                event.image = f'uploads/events/{filename}'
        
        db.session.commit()
        
        flash('Event updated successfully.', 'success')
        return redirect(url_for('admin.events'))
    
    return render_template('admin/edit_event.html', event=event)

@admin_bp.route('/events/delete/<int:event_id>')
@login_required
@admin_required
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    
    flash('Event deleted successfully.', 'success')
    return redirect(url_for('admin.events'))

@admin_bp.route('/projects/edit/<int:project_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        project.title = request.form.get('title')
        project.description = request.form.get('description')
        project.image = request.form.get('image')
        project.github_link = request.form.get('github_link')
        project.demo_link = request.form.get('demo_link')
        project.technologies = request.form.get('technologies')
        # Handle multi-select team members
        selected_members = request.form.getlist('team_members')
        project.team_members = ', '.join(selected_members) if selected_members else ''
        project.is_featured = 'is_featured' in request.form
        db.session.commit()
        
        flash('Project updated successfully.', 'success')
        return redirect(url_for('admin.projects'))
    
    # Get all approved members for the dropdown
    members = Member.query.join(User).filter(User.is_approved == True).order_by(Member.full_name.asc()).all()
    
    # Get all active technologies for the dropdown
    technologies = Technology.query.filter_by(is_active=True).order_by(Technology.category.asc(), Technology.name.asc()).all()
    
    return render_template('admin/edit_project.html', project=project, members=members, technologies=technologies)

@admin_bp.route('/projects/delete/<int:project_id>')
@login_required
@admin_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    
    flash('Project deleted successfully.', 'success')
    return redirect(url_for('admin.projects'))

@admin_bp.route('/gallery/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_gallery_item(item_id):
    item = Gallery.query.get_or_404(item_id)
    
    if request.method == 'POST':
        item.type = request.form.get('type')
        item.url = request.form.get('url')
        item.caption = request.form.get('caption')
        db.session.commit()
        
        flash('Gallery item updated successfully.', 'success')
        return redirect(url_for('admin.gallery'))
    
    return render_template('admin/edit_gallery_item.html', item=item)

@admin_bp.route('/gallery/delete/<int:item_id>')
@login_required
@admin_required
def delete_gallery_item(item_id):
    item = Gallery.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    
    flash('Gallery item deleted successfully.', 'success')
    return redirect(url_for('admin.gallery'))

# Leader Management Routes
@admin_bp.route('/leaders')
@login_required
@admin_required
def leaders():
    from sqlalchemy.orm import joinedload
    leaders = Leader.query.options(joinedload(Leader.user).joinedload(User.member)).order_by(Leader.display_order.asc()).all()
    
    # Debug: Print leader count
    print(f"DEBUG: Found {len(leaders)} leaders")
    for leader in leaders:
        print(f"  - Leader ID: {leader.id}, Position: {leader.position}")
        print(f"    User ID: {leader.user_id}, Has User: {leader.user is not None}")
        if leader.user:
            print(f"    User Email: {leader.user.email}, Has Member: {leader.user.member is not None}")
            if leader.user.member:
                print(f"    Member Name: {leader.user.member.full_name}")
    
    return render_template('admin/leaders.html', leaders=leaders)

@admin_bp.route('/leaders/debug')
@login_required
@admin_required
def debug_leaders():
    """Debug route to check leaders in database"""
    all_leaders = Leader.query.all()
    leaders_with_users = Leader.query.join(User).all()
    leaders_with_members = Leader.query.join(User).join(Member).all()
    
    debug_info = {
        'total_leaders': len(all_leaders),
        'leaders_with_users': len(leaders_with_users),
        'leaders_with_members': len(leaders_with_members),
        'leaders': []
    }
    
    for leader in all_leaders:
        debug_info['leaders'].append({
            'id': leader.id,
            'user_id': leader.user_id,
            'position': leader.position,
            'has_user': leader.user is not None,
            'has_member': leader.user.member is not None if leader.user else False,
            'user_email': leader.user.email if leader.user else None,
            'member_name': leader.user.member.full_name if leader.user and leader.user.member else None
        })
    
    return f"<pre>{debug_info}</pre>"

@admin_bp.route('/leaders/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_leader():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        position = request.form.get('position')
        display_order = request.form.get('display_order', 0, type=int)
        
        # Check if user already has a leadership position
        existing_leader = Leader.query.filter_by(user_id=user_id).first()
        if existing_leader:
            flash('This user already has a leadership position.', 'warning')
            return redirect(url_for('admin.add_leader'))
        
        leader = Leader(
            user_id=user_id,
            position=position,
            display_order=display_order
        )
        
        db.session.add(leader)
        db.session.commit()
        
        flash('Leader added successfully.', 'success')
        return redirect(url_for('admin.leaders'))
    
    # Get all approved members who are not already leaders
    existing_leader_ids = [l.user_id for l in Leader.query.all()]
    members = Member.query.join(User).filter(
        User.is_approved == True,
        ~Member.user_id.in_(existing_leader_ids)
    ).all()
    
    # Debug: Print member count
    print(f"DEBUG: Found {len(members)} available members for leadership")
    for member in members:
        print(f"  - {member.full_name} ({member.user.email})")
    
    return render_template('admin/add_leader.html', members=members)

@admin_bp.route('/leaders/edit/<int:leader_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_leader(leader_id):
    leader = Leader.query.get_or_404(leader_id)
    
    if request.method == 'POST':
        leader.position = request.form.get('position')
        leader.display_order = request.form.get('display_order', 0, type=int)
        
        db.session.commit()
        
        flash('Leader updated successfully.', 'success')
        return redirect(url_for('admin.leaders'))
    
    return render_template('admin/edit_leader.html', leader=leader)

@admin_bp.route('/leaders/delete/<int:leader_id>')
@login_required
@admin_required
def delete_leader(leader_id):
    leader = Leader.query.get_or_404(leader_id)
    db.session.delete(leader)
    db.session.commit()
    
    flash('Leader removed successfully.', 'success')
    return redirect(url_for('admin.leaders'))

# Blog Management Routes
@admin_bp.route('/blogs')
@login_required
@admin_required
def blogs():
    blogs = Blog.query.order_by(Blog.created_at.desc()).all()
    return render_template('admin/blogs.html', blogs=blogs)

@admin_bp.route('/blogs/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_blog():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        excerpt = request.form.get('excerpt')
        category = request.form.get('category')
        tags = request.form.get('tags')
        is_published = 'is_published' in request.form
        
        # Handle image URL
        featured_image = request.form.get('featured_image', '').strip()
        if not featured_image:
            featured_image = None
        
        # Generate slug from title
        slug = title.lower().replace(' ', '-').replace('&', 'and')
        slug = ''.join(c for c in slug if c.isalnum() or c in '-')
        
        # Ensure unique slug
        original_slug = slug
        counter = 1
        while Blog.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        blog = Blog(
            title=title,
            slug=slug,
            content=content,
            excerpt=excerpt,
            author_id=current_user.id,
            category=category,
            tags=tags,
            featured_image=featured_image,
            is_published=is_published,
            published_date=datetime.utcnow() if is_published else None
        )
        
        db.session.add(blog)
        db.session.commit()
        
        flash('Blog post created successfully.', 'success')
        return redirect(url_for('admin.blogs'))
    
    return render_template('admin/add_blog.html')

@admin_bp.route('/blogs/edit/<int:blog_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_blog(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    
    if request.method == 'POST':
        blog.title = request.form.get('title')
        blog.content = request.form.get('content')
        blog.excerpt = request.form.get('excerpt')
        blog.category = request.form.get('category')
        blog.tags = request.form.get('tags')
        blog.is_published = 'is_published' in request.form
        
        # Handle image removal
        if 'remove_image' in request.form:
            if blog.featured_image:
                # Only delete if it's a local file (not a URL)
                if not (blog.featured_image.startswith('http://') or blog.featured_image.startswith('https://')):
                    old_image_path = os.path.join(current_app.static_folder, blog.featured_image)
                    if os.path.exists(old_image_path):
                        try:
                            os.remove(old_image_path)
                        except:
                            pass  # If deletion fails, continue anyway
                blog.featured_image = None
        else:
            # Handle new image URL
            featured_image_url = request.form.get('featured_image', '').strip()
            if featured_image_url:
                # Only delete old local file if it exists and is being replaced
                if blog.featured_image and not (blog.featured_image.startswith('http://') or blog.featured_image.startswith('https://')):
                    old_image_path = os.path.join(current_app.static_folder, blog.featured_image)
                    if os.path.exists(old_image_path):
                        try:
                            os.remove(old_image_path)
                        except:
                            pass
                blog.featured_image = featured_image_url
            elif not blog.featured_image:
                # If no URL provided and no existing image, set to None
                blog.featured_image = None
        
        if blog.is_published and not blog.published_date:
            blog.published_date = datetime.utcnow()
        
        db.session.commit()
        
        flash('Blog post updated successfully.', 'success')
        return redirect(url_for('admin.blogs'))
    
    return render_template('admin/edit_blog.html', blog=blog)

@admin_bp.route('/blogs/delete/<int:blog_id>')
@login_required
@admin_required
def delete_blog(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    db.session.delete(blog)
    db.session.commit()
    
    flash('Blog post deleted successfully.', 'success')
    return redirect(url_for('admin.blogs'))

# RSVP Management Routes
@admin_bp.route('/rsvps')
@login_required
@admin_required
def rsvps():
    event_id = request.args.get('event_id', type=int)
    status_filter = request.args.get('status', '')
    
    query = RSVP.query.join(Event)
    
    if event_id:
        query = query.filter(RSVP.event_id == event_id)
    if status_filter:
        query = query.filter(RSVP.status == status_filter)
    
    rsvps = query.order_by(RSVP.submitted_at.desc()).all()
    events = Event.query.order_by(Event.event_date.desc()).all()
    
    return render_template('admin/rsvps.html', rsvps=rsvps, events=events, 
                         current_event_id=event_id, current_status=status_filter)

@admin_bp.route('/rsvps/approve/<int:rsvp_id>')
@login_required
@admin_required
def approve_rsvp(rsvp_id):
    rsvp = RSVP.query.get_or_404(rsvp_id)
    rsvp.status = 'approved'
    rsvp.approved_at = datetime.utcnow()
    rsvp.approved_by = current_user.id
    rsvp.generate_acceptance_code()
    
    db.session.commit()
    
    # Send notification (email/SMS)
    send_rsvp_notification(rsvp, 'approved')
    
    flash(f'RSVP for {rsvp.full_name} has been approved. Acceptance code: {rsvp.acceptance_code}', 'success')
    return redirect(url_for('admin.rsvps'))

@admin_bp.route('/rsvps/reject/<int:rsvp_id>')
@login_required
@admin_required
def reject_rsvp(rsvp_id):
    rsvp = RSVP.query.get_or_404(rsvp_id)
    rsvp.status = 'rejected'
    rsvp.approved_at = datetime.utcnow()
    rsvp.approved_by = current_user.id
    
    db.session.commit()
    
    # Send notification (email/SMS)
    send_rsvp_notification(rsvp, 'rejected')
    
    flash(f'RSVP for {rsvp.full_name} has been rejected.', 'success')
    return redirect(url_for('admin.rsvps'))

@admin_bp.route('/rsvps/disapprove/<int:rsvp_id>')
@login_required
@admin_required
def disapprove_rsvp(rsvp_id):
    rsvp = RSVP.query.get_or_404(rsvp_id)
    
    # Reset RSVP to pending status
    rsvp.status = 'pending'
    rsvp.approved_at = None
    rsvp.approved_by = None
    rsvp.acceptance_code = None
    
    db.session.commit()
    
    flash(f'RSVP for {rsvp.full_name} has been reset to pending status.', 'success')
    return redirect(url_for('admin.rsvps'))

@admin_bp.route('/rsvps/bulk-approve', methods=['POST'])
@login_required
@admin_required
def bulk_approve_rsvps():
    data = request.get_json() or {}
    rsvp_ids = data.get('rsvp_ids', [])
    limit = data.get('limit', None)
    count = 0
    
    # If limit is provided and no rsvp_ids, get first N pending RSVPs
    if limit and not rsvp_ids:
        # Get current filter parameters from query string or JSON
        event_id = request.args.get('event_id', type=int) or data.get('event_id')
        status_filter = request.args.get('status', '') or data.get('status', '')
        
        query = RSVP.query.join(Event)
        
        if event_id:
            query = query.filter(RSVP.event_id == event_id)
        if status_filter:
            query = query.filter(RSVP.status == status_filter)
        else:
            # Default to pending if no status filter
            query = query.filter(RSVP.status == 'pending')
        
        # Get first N pending RSVPs
        rsvps = query.filter(RSVP.status == 'pending').order_by(RSVP.submitted_at.asc()).limit(limit).all()
        rsvp_ids = [rsvp.id for rsvp in rsvps]
    
    for rsvp_id in rsvp_ids:
        rsvp = RSVP.query.get(rsvp_id)
        if rsvp and rsvp.status == 'pending':
            rsvp.status = 'approved'
            rsvp.approved_at = datetime.utcnow()
            rsvp.approved_by = current_user.id
            rsvp.generate_acceptance_code()
            count += 1
    
    db.session.commit()
    
    # Send notifications for all approved RSVPs
    if rsvp_ids:
        approved_rsvps = RSVP.query.filter(RSVP.id.in_(rsvp_ids), RSVP.status == 'approved').all()
        for rsvp in approved_rsvps:
            send_rsvp_notification(rsvp, 'approved')
    
    return jsonify({'success': True, 'message': f'{count} RSVPs approved successfully'})

@admin_bp.route('/rsvps/bulk-reject', methods=['POST'])
@login_required
@admin_required
def bulk_reject_rsvps():
    data = request.get_json() or {}
    rsvp_ids = data.get('rsvp_ids', [])
    limit = data.get('limit', None)
    count = 0
    
    # If limit is provided and no rsvp_ids, get first N pending RSVPs
    if limit and not rsvp_ids:
        # Get current filter parameters from query string or JSON
        event_id = request.args.get('event_id', type=int) or data.get('event_id')
        status_filter = request.args.get('status', '') or data.get('status', '')
        
        query = RSVP.query.join(Event)
        
        if event_id:
            query = query.filter(RSVP.event_id == event_id)
        if status_filter:
            query = query.filter(RSVP.status == status_filter)
        else:
            # Default to pending if no status filter
            query = query.filter(RSVP.status == 'pending')
        
        # Get first N pending RSVPs
        rsvps = query.filter(RSVP.status == 'pending').order_by(RSVP.submitted_at.asc()).limit(limit).all()
        rsvp_ids = [rsvp.id for rsvp in rsvps]
    
    for rsvp_id in rsvp_ids:
        rsvp = RSVP.query.get(rsvp_id)
        if rsvp and rsvp.status == 'pending':
            rsvp.status = 'rejected'
            rsvp.approved_at = datetime.utcnow()
            rsvp.approved_by = current_user.id
            count += 1
    
    db.session.commit()
    
    # Send notifications for all rejected RSVPs
    if rsvp_ids:
        rejected_rsvps = RSVP.query.filter(RSVP.id.in_(rsvp_ids), RSVP.status == 'rejected').all()
        for rsvp in rejected_rsvps:
            send_rsvp_notification(rsvp, 'rejected')
    
    return jsonify({'success': True, 'message': f'{count} RSVPs rejected successfully'})

@admin_bp.route('/rsvps/bulk-disapprove', methods=['POST'])
@login_required
@admin_required
def bulk_disapprove_rsvps():
    data = request.get_json() or {}
    rsvp_ids = data.get('rsvp_ids', [])
    limit = data.get('limit', None)
    count = 0
    
    # If limit is provided and no rsvp_ids, get first N approved/rejected RSVPs
    if limit and not rsvp_ids:
        # Get current filter parameters from query string or JSON
        event_id = request.args.get('event_id', type=int) or data.get('event_id')
        status_filter = request.args.get('status', '') or data.get('status', '')
        
        query = RSVP.query.join(Event)
        
        if event_id:
            query = query.filter(RSVP.event_id == event_id)
        if status_filter:
            query = query.filter(RSVP.status == status_filter)
        else:
            # Default to approved/rejected if no status filter
            query = query.filter(RSVP.status.in_(['approved', 'rejected']))
        
        # Get first N approved/rejected RSVPs
        rsvps = query.filter(RSVP.status.in_(['approved', 'rejected'])).order_by(RSVP.submitted_at.asc()).limit(limit).all()
        rsvp_ids = [rsvp.id for rsvp in rsvps]
    
    for rsvp_id in rsvp_ids:
        rsvp = RSVP.query.get(rsvp_id)
        if rsvp and rsvp.status in ['approved', 'rejected']:
            rsvp.status = 'pending'
            rsvp.approved_at = None
            rsvp.approved_by = None
            rsvp.acceptance_code = None
            count += 1
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'{count} RSVPs reset to pending successfully'})

# Technology Management Routes
@admin_bp.route('/technologies')
@login_required
@admin_required
def technologies():
    category_filter = request.args.get('category', '')
    
    query = Technology.query
    if category_filter:
        query = query.filter_by(category=category_filter)
    
    technologies = query.order_by(Technology.category.asc(), Technology.name.asc()).all()
    
    # Get all categories for filter dropdown
    categories = db.session.query(Technology.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('admin/technologies.html', 
                         technologies=technologies,
                         categories=categories,
                         current_category=category_filter)

@admin_bp.route('/technologies/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_technology():
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        description = request.form.get('description')
        icon = request.form.get('icon')
        is_active = 'is_active' in request.form
        
        # Check if technology already exists
        existing = Technology.query.filter_by(name=name).first()
        if existing:
            flash('A technology with this name already exists.', 'warning')
            return redirect(url_for('admin.add_technology'))
        
        technology = Technology(
            name=name,
            category=category,
            description=description,
            icon=icon,
            is_active=is_active
        )
        
        db.session.add(technology)
        db.session.commit()
        
        flash('Technology added successfully.', 'success')
        return redirect(url_for('admin.technologies'))
    
    return render_template('admin/add_technology.html')

@admin_bp.route('/technologies/edit/<int:tech_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_technology(tech_id):
    technology = Technology.query.get_or_404(tech_id)
    
    if request.method == 'POST':
        technology.name = request.form.get('name')
        technology.category = request.form.get('category')
        technology.description = request.form.get('description')
        technology.icon = request.form.get('icon')
        technology.is_active = 'is_active' in request.form
        
        db.session.commit()
        
        flash('Technology updated successfully.', 'success')
        return redirect(url_for('admin.technologies'))
    
    return render_template('admin/edit_technology.html', technology=technology)

@admin_bp.route('/technologies/delete/<int:tech_id>')
@login_required
@admin_required
def delete_technology(tech_id):
    technology = Technology.query.get_or_404(tech_id)
    db.session.delete(technology)
    db.session.commit()
    
    flash('Technology deleted successfully.', 'success')
    return redirect(url_for('admin.technologies'))

@admin_bp.route('/technologies/toggle-status/<int:tech_id>')
@login_required
@admin_required
def toggle_technology_status(tech_id):
    technology = Technology.query.get_or_404(tech_id)
    technology.is_active = not technology.is_active
    db.session.commit()
    
    status = 'activated' if technology.is_active else 'deactivated'
    flash(f'Technology {status} successfully.', 'success')
    return redirect(url_for('admin.technologies'))

def send_rsvp_notification(rsvp, status):
    """Send email/SMS notification for RSVP status change"""
    try:
        notification_service = get_notification_service()
        result = notification_service.send_rsvp_notification(rsvp, status)
        
        if result.get('email_sent'):
            current_app.logger.info(f"Email notification sent to {rsvp.email}")
        else:
            current_app.logger.warning(f"Failed to send email notification to {rsvp.email}")
        
        if result.get('sms_sent'):
            current_app.logger.info(f"SMS notification sent to {rsvp.phone}")
        elif rsvp.phone:
            current_app.logger.warning(f"Failed to send SMS notification to {rsvp.phone}")
        
        return result
        
    except Exception as e:
        current_app.logger.error(f"Failed to send notification: {e}")
        return {'email_sent': False, 'sms_sent': False, 'error': str(e)}


# ============================================================================
# MEMBER MANAGEMENT ROUTES
# ============================================================================

def _verify_admin_password_or_redirect(member_id):
    admin_password = (request.form.get('admin_password') or '').strip()
    if not admin_password:
        flash('Admin password is required for this action.', 'error')
        return redirect(url_for('admin.members'))
    if not current_user.check_password(admin_password):
        flash('Invalid admin password.', 'error')
        return redirect(url_for('admin.members'))
    return None


def _delete_member_account_data(user):
    """Delete student account data safely across related tables."""
    member = user.member
    if member:
        member_id = member.id

        # Remove score rows tied to this member's submissions first.
        submission_ids = [sid for (sid,) in db.session.query(CompetitionSubmission.id).filter_by(member_id=member_id).all()]
        if submission_ids:
            CompetitionScore.query.filter(CompetitionScore.submission_id.in_(submission_ids)).delete(synchronize_session=False)

        CompetitionSubmission.query.filter_by(member_id=member_id).delete(synchronize_session=False)
        CompetitionWinner.query.filter_by(member_id=member_id).delete(synchronize_session=False)
        CompetitionGuard.query.filter_by(member_id=member_id).delete(synchronize_session=False)
        CompetitionEnrollment.query.filter_by(member_id=member_id).delete(synchronize_session=False)
        TeamMember.query.filter_by(member_id=member_id).delete(synchronize_session=False)
        MembershipPayment.query.filter_by(member_id=member_id).delete(synchronize_session=False)
        MemberTrophy.query.filter_by(member_id=member_id).delete(synchronize_session=False)
        RewardTransaction.query.filter_by(member_id=member_id).delete(synchronize_session=False)
        RSVP.query.filter_by(member_id=member_id).delete(synchronize_session=False)
        Project.query.filter_by(member_id=member_id).delete(synchronize_session=False)

        db.session.delete(member)

    # Remove user-linked technical/assignment rows.
    CompetitionScore.query.filter_by(judge_id=user.id).delete(synchronize_session=False)
    CompetitionJudge.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    CompetitionEnrollment.query.filter_by(disqualified_by=user.id).update({'disqualified_by': None}, synchronize_session=False)
    RSVP.query.filter_by(approved_by=user.id).update({'approved_by': None}, synchronize_session=False)
    RSVP.query.filter_by(checked_in_by=user.id).update({'checked_in_by': None}, synchronize_session=False)
    SessionReport.query.filter_by(winner_user_id=user.id).update({'winner_user_id': None}, synchronize_session=False)
    SessionReport.query.filter_by(approved_by=user.id).update({'approved_by': None}, synchronize_session=False)

    # If this user instructed sessions, remove reports then sessions.
    session_ids = [sid for (sid,) in db.session.query(SessionSchedule.id).filter_by(instructor_user_id=user.id).all()]
    if session_ids:
        SessionReport.query.filter(SessionReport.session_id.in_(session_ids)).delete(synchronize_session=False)
        SessionSchedule.query.filter(SessionSchedule.id.in_(session_ids)).delete(synchronize_session=False)
    SessionReport.query.filter_by(instructor_user_id=user.id).delete(synchronize_session=False)

    db.session.delete(user)

@admin_bp.route('/members')
@login_required
@admin_required
def members():
    """View all members with payment status and role filters"""
    status_filter = request.args.get('status', 'all')  # all, valid, expired, none
    role_filter = request.args.get('role', 'all')  # all, admin, member
    search = request.args.get('search', '')
    course_filter = request.args.get('course', '')
    year_filter = request.args.get('year', '')
    page = request.args.get('page', 1, type=int) or 1
    per_page = request.args.get('per_page', 20, type=int) or 20
    per_page = max(10, min(per_page, 100))
    
    query = Member.query.join(User).filter(User.is_approved == True)
    
    # Apply role filter
    if role_filter == 'admin':
        query = query.filter(User.role == 'admin')
    elif role_filter == 'member':
        query = query.filter(User.role == 'student')
    
    # Apply course filter
    if course_filter:
        query = query.filter(Member.course.ilike(f'%{course_filter}%'))
    
    # Apply year filter
    if year_filter:
        query = query.filter(Member.year.ilike(f'%{year_filter}%'))
    
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                Member.full_name.ilike(f'%{search}%'),
                Member.member_id_number.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    members = query.order_by(Member.full_name.asc()).all()
    
    # Filter by payment status
    if status_filter != 'all':
        filtered_members = []
        for member in members:
            member_status = member.get_membership_status()
            if status_filter == member_status:
                filtered_members.append(member)
        members = filtered_members
    
    # Paginate filtered members list
    total_filtered = len(members)
    total_pages = max((total_filtered + per_page - 1) // per_page, 1)
    if page > total_pages:
        page = total_pages
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    members_page = members[start_idx:end_idx]

    # Get statistics
    all_members = Member.query.join(User).filter(User.is_approved == True).all()
    total_members = len(all_members)
    valid_count = sum(1 for m in all_members if m.get_membership_status() == 'valid')
    expired_count = sum(1 for m in all_members if m.get_membership_status() == 'expired')
    none_count = sum(1 for m in all_members if m.get_membership_status() == 'none')
    
    # Role statistics
    admin_count = sum(1 for m in all_members if m.user.role == 'admin')
    member_count = sum(1 for m in all_members if m.user.role == 'student')
    super_admin_count = sum(1 for m in all_members if m.user.is_super_admin)
    
    # Get unique courses and years for filter dropdowns
    courses = db.session.query(Member.course).filter(
        Member.user_id.in_(db.session.query(User.id).filter(User.is_approved == True))
    ).distinct().all()
    years = db.session.query(Member.year).filter(
        Member.user_id.in_(db.session.query(User.id).filter(User.is_approved == True))
    ).distinct().all()
    
    return render_template('admin/members.html',
                         members=members_page,
                         current_status=status_filter,
                         current_role=role_filter,
                         search_query=search,
                         current_course=course_filter,
                         current_year=year_filter,
                         courses=[c[0] for c in courses if c[0]],
                         years=[y[0] for y in years if y[0]],
                         total_members=total_members,
                         valid_count=valid_count,
                         expired_count=expired_count,
                         none_count=none_count,
                         admin_count=admin_count,
                         member_count=member_count,
                         super_admin_count=super_admin_count,
                         page=page,
                         per_page=per_page,
                         total_filtered=total_filtered,
                         total_pages=total_pages)


@admin_bp.route('/members/export')
@login_required
@admin_required
def export_members():
    """Export members/users as CSV report"""
    report_type = request.args.get('report_type', 'filtered')  # all_users, all_members, filtered
    status_filter = request.args.get('status', 'all')
    role_filter = request.args.get('role', 'all')
    search = request.args.get('search', '')
    course_filter = request.args.get('course', '')
    year_filter = request.args.get('year', '')
    
    # Build query based on report type
    if report_type == 'all_users' or report_type == 'all_members':
        # Get all approved members regardless of filters
        query = Member.query.join(User).filter(User.is_approved == True)
    else:
        # Apply filters for filtered report
        query = Member.query.join(User).filter(User.is_approved == True)
        
        # Apply role filter
        if role_filter == 'admin':
            query = query.filter(User.role == 'admin')
        elif role_filter == 'member':
            query = query.filter(User.role == 'student')
        
        # Apply course filter
        if course_filter:
            query = query.filter(Member.course.ilike(f'%{course_filter}%'))
        
        # Apply year filter
        if year_filter:
            query = query.filter(Member.year.ilike(f'%{year_filter}%'))
        
        # Apply search filter
        if search:
            query = query.filter(
                db.or_(
                    Member.full_name.ilike(f'%{search}%'),
                    Member.member_id_number.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )
    
    members = query.order_by(Member.full_name.asc()).all()
    
    # Filter by payment status if not all_users/all_members
    if report_type == 'filtered' and status_filter != 'all':
        filtered_members = []
        for member in members:
            member_status = member.get_membership_status()
            if status_filter == member_status:
                filtered_members.append(member)
        members = filtered_members
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Member ID Number',
        'Full Name',
        'Email',
        'Phone',
        'Course',
        'Year',
        'Status',
        'Role',
        'Membership Status',
        'Total Points',
        'Member Since',
        'Title',
        'GitHub',
        'LinkedIn'
    ])
    
    # Write data rows
    for member in members:
        membership_status = member.get_membership_status()
        role = 'Super Admin' if member.user.is_super_admin else ('Admin' if member.user.role == 'admin' else 'Member')
        
        writer.writerow([
            member.member_id_number or '',
            member.full_name or '',
            member.user.email or '',
            member.phone or '',
            member.course or '',
            member.year or '',
            member.status or '',
            role,
            membership_status,
            member.get_total_points(),
            member.created_at.strftime('%Y-%m-%d') if member.created_at else '',
            member.title or '',
            member.github or '',
            member.linkedin or ''
        ])
    
    # Create response
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'members_report_{report_type}_{timestamp}.csv'
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response


@admin_bp.route('/member-ids')
@login_required
@admin_required
def member_ids():
    """View all member digital IDs with flip functionality"""
    search = request.args.get('search', '')
    status_filter = request.args.get('status', 'all')  # all, valid, expired, none
    
    # Query members with digital IDs
    query = Member.query.join(User).filter(
        User.is_approved == True,
        Member.digital_id_path.isnot(None)
    )
    
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                Member.full_name.ilike(f'%{search}%'),
                Member.member_id_number.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    members = query.order_by(Member.full_name.asc()).all()
    
    # Filter by payment status if needed
    if status_filter != 'all':
        filtered_members = []
        for member in members:
            member_status = member.get_membership_status()
            if status_filter == member_status:
                filtered_members.append(member)
        members = filtered_members
    
    # Get statistics
    all_members_with_ids = Member.query.join(User).filter(
        User.is_approved == True,
        Member.digital_id_path.isnot(None)
    ).all()
    
    total_with_ids = len(all_members_with_ids)
    
    return render_template('admin/member_ids.html',
                         members=members,
                         search_query=search,
                         current_status=status_filter,
                         total_with_ids=total_with_ids)


@admin_bp.route('/member-ids/export-pdf')
@login_required
@admin_required
def export_member_ids_pdf():
    """Export member IDs as PDF bundle"""
    layout = request.args.get('layout', 'bundle')  # single, standard, bundle
    page_size = request.args.get('page_size', 'letter')  # letter, a4
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '')
    
    # Query members with digital IDs
    query = Member.query.join(User).filter(
        User.is_approved == True,
        Member.digital_id_path.isnot(None)
    )
    
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                Member.full_name.ilike(f'%{search}%'),
                Member.member_id_number.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    members = query.order_by(Member.full_name.asc()).all()
    
    # Filter by payment status if needed
    if status_filter != 'all':
        filtered_members = []
        for member in members:
            member_status = member.get_membership_status()
            if status_filter == member_status:
                filtered_members.append(member)
        members = filtered_members
    
    try:
        # Generate PDF
        pdf_buffer = generate_member_ids_pdf(members, layout=layout, page_size=page_size)
        
        # Create response
        from flask import Response
        filename = f"member_ids_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        response = Response(
            pdf_buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generating PDF: {str(e)}")
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('admin.member_ids'))


@admin_bp.route('/members/<int:member_id>')
@login_required
@admin_required
def member_detail(member_id):
    """View detailed member information"""
    member = Member.query.get_or_404(member_id)
    
    # Get member statistics
    total_points = member.get_total_points()
    trophies = member.get_current_trophies()
    membership_status = member.get_membership_status()
    
    # Get recent transactions
    recent_transactions = member.reward_transactions.order_by(RewardTransaction.created_at.desc()).limit(10).all()
    
    # Get payment history
    payments = member.membership_payments.order_by(MembershipPayment.payment_date.desc()).all()
    
    # Get attendance history (checked-in RSVPs)
    attendance = RSVP.query.filter_by(member_id=member.id, checked_in=True).order_by(RSVP.checked_in_at.desc()).limit(10).all()
    
    # Get all trophies for progress tracking
    all_trophies = Trophy.query.filter_by(is_active=True).order_by(Trophy.points_required.asc()).all()
    
    return render_template('admin/member_detail.html',
                         member=member,
                         total_points=total_points,
                         trophies=trophies,
                         membership_status=membership_status,
                         recent_transactions=recent_transactions,
                         payments=payments,
                         attendance=attendance,
                         all_trophies=all_trophies)


@admin_bp.route('/members/<int:member_id>/promote', methods=['POST'])
@login_required
@admin_required
def promote_member(member_id):
    """Promote a member to admin"""
    member = Member.query.get_or_404(member_id)
    user = member.user
    
    if user.role == 'admin':
        flash(f'{member.full_name} is already an admin.', 'warning')
        return redirect(url_for('admin.members'))
    
    user.role = 'admin'
    db.session.commit()

    try:
        notification_service = get_notification_service()
        notification_service.send_admin_promotion_email(user, current_user)
    except Exception as exc:
        current_app.logger.error(f"Failed to send admin promotion email for {user.email}: {exc}")
    
    flash(f'{member.full_name} has been promoted to admin!', 'success')
    return redirect(url_for('admin.members'))


@admin_bp.route('/members/<int:member_id>/demote', methods=['POST'])
@login_required
@admin_required
def demote_member(member_id):
    """Demote an admin to regular member"""
    member = Member.query.get_or_404(member_id)
    user = member.user
    
    if user.is_super_admin:
        flash('Cannot demote super admin!', 'error')
        return redirect(url_for('admin.members'))
    
    if user.role != 'admin':
        flash(f'{member.full_name} is not an admin.', 'warning')
        return redirect(url_for('admin.members'))
    
    user.role = 'student'
    db.session.commit()
    
    flash(f'{member.full_name} has been demoted to regular member.', 'success')
    return redirect(url_for('admin.members'))


@admin_bp.route('/members/<int:member_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_member_active(member_id):
    redirect_resp = _verify_admin_password_or_redirect(member_id)
    if redirect_resp:
        return redirect_resp

    member = Member.query.get_or_404(member_id)
    user = member.user
    if not user:
        flash('Member account not found.', 'error')
        return redirect(url_for('admin.members'))
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('admin.members'))
    if user.is_super_admin:
        flash('Super admin account cannot be deactivated.', 'error')
        return redirect(url_for('admin.members'))

    user.is_active_account = not bool(user.is_active_account)
    db.session.commit()
    state = 'activated' if user.is_active_account else 'deactivated'
    flash(f'{member.full_name} account has been {state}.', 'success')
    return redirect(url_for('admin.members'))


@admin_bp.route('/members/<int:member_id>/delete-account', methods=['POST'])
@login_required
@admin_required
def delete_member_account(member_id):
    redirect_resp = _verify_admin_password_or_redirect(member_id)
    if redirect_resp:
        return redirect_resp

    member = Member.query.get_or_404(member_id)
    user = member.user
    if not user:
        flash('Member account not found.', 'error')
        return redirect(url_for('admin.members'))
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.members'))
    if user.is_super_admin:
        flash('Super admin account cannot be deleted.', 'error')
        return redirect(url_for('admin.members'))
    if user.role == 'admin':
        flash('Admin accounts cannot be deleted from this page. Demote first if needed.', 'error')
        return redirect(url_for('admin.members'))

    try:
        display_name = member.full_name
        _delete_member_account_data(user)
        db.session.commit()
        flash(f'{display_name} account and related records were deleted.', 'success')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Failed deleting member account')
        flash(f'Failed to delete account: {exc}', 'error')
    return redirect(url_for('admin.members'))


@admin_bp.route('/profile')
@login_required
@admin_required
def admin_profile():
    """View current admin's profile"""
    member = current_user.member
    if not member:
        flash('Profile not found. Please complete your member profile.', 'error')
        return redirect(url_for('admin.dashboard'))
    
    # Get member statistics
    total_points = member.get_total_points()
    trophies = member.get_current_trophies()
    membership_status = member.get_membership_status()
    
    # Get recent transactions
    recent_transactions = member.reward_transactions.order_by(RewardTransaction.created_at.desc()).limit(10).all()
    
    # Get payment history
    payments = member.membership_payments.order_by(MembershipPayment.payment_date.desc()).all()
    
    # Get attendance history
    attendance = RSVP.query.filter_by(member_id=member.id, checked_in=True).order_by(RSVP.checked_in_at.desc()).limit(10).all()
    
    # Get all trophies for progress tracking
    all_trophies = Trophy.query.filter_by(is_active=True).order_by(Trophy.points_required.asc()).all()
    
    return render_template('admin/admin_profile.html',
                         member=member,
                         total_points=total_points,
                         trophies=trophies,
                         membership_status=membership_status,
                         recent_transactions=recent_transactions,
                         payments=payments,
                         attendance=attendance,
                         all_trophies=all_trophies)


# ============================================================================
# REWARDS SYSTEM ROUTES
# ============================================================================

@admin_bp.route('/rewards/scan')
@login_required
@admin_required
def scan_id():
    """ID scanner page for manual entry and QR code scanning"""
    return render_template('admin/scan_id.html')


@admin_bp.route('/rewards/member-lookup', methods=['POST'])
@login_required
@admin_required
def member_lookup():
    """AJAX endpoint to lookup member by ID number"""
    member_id_number = request.json.get('member_id_number', '').strip()
    
    if not member_id_number:
        return jsonify({'success': False, 'error': 'Member ID is required'})
    
    member = Member.query.filter_by(member_id_number=member_id_number).first()
    
    if not member:
        return jsonify({'success': False, 'error': 'Member not found'})
    
    # Get member data
    total_points = member.get_total_points()
    membership_status = member.get_membership_status()
    trophies = member.get_current_trophies()
    latest_payment = member.get_latest_payment()
    recent_attendance = RSVP.query.filter_by(member_id=member.id, checked_in=True).order_by(RSVP.checked_in_at.desc()).limit(5).all()
    
    return jsonify({
        'success': True,
        'member': {
            'id': member.id,
            'member_id_number': member.member_id_number,
            'full_name': member.full_name,
            'email': member.user.email,
            'phone': member.phone,
            'profile_image': member.profile_image,
            'course': member.course,
            'year': member.year,
            'status': member.status,
            'total_points': total_points,
            'membership_status': membership_status,
            'trophies': [{'name': t.name, 'icon': t.icon} for t in trophies],
            'latest_payment': {
                'amount': latest_payment.amount,
                'end_date': latest_payment.end_date.strftime('%Y-%m-%d'),
                'days_remaining': latest_payment.days_remaining()
            } if latest_payment else None,
            'recent_attendance': [
                {
                    'event': a.event.title,
                    'date': a.checked_in_at.strftime('%Y-%m-%d')
                } for a in recent_attendance
            ]
        }
    })


@admin_bp.route('/members/search')
@login_required
@admin_required
def members_search():
    """Live search endpoint for approved members/users."""
    q = (request.args.get('q') or '').strip()
    limit = request.args.get('limit', default=12, type=int) or 12
    limit = max(1, min(limit, 50))

    query = Member.query.join(User).filter(User.is_approved == True)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Member.full_name.ilike(like),
                Member.member_id_number.ilike(like),
                User.email.ilike(like),
                Member.course.ilike(like),
            )
        )

    members = query.order_by(Member.full_name.asc()).limit(limit).all()
    return jsonify({
        'results': [
            {
                'id': m.id,
                'user_id': m.user_id,
                'full_name': m.full_name,
                'email': m.user.email if m.user else '',
                'member_id_number': m.member_id_number or '',
                'course': m.course or '',
                'year': m.year or '',
                'member_detail_url': url_for('admin.member_detail', member_id=m.id),
                'add_points_url': url_for('admin.add_points', member_id=m.id),
            }
            for m in members
        ]
    })


@admin_bp.route('/rewards/add-points/<int:member_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def add_points(member_id):
    """Award or deduct points from a member"""
    member = Member.query.get_or_404(member_id)
    
    if request.method == 'POST':
        points = request.form.get('points', type=int)
        transaction_type = request.form.get('transaction_type', 'manual')
        reason = request.form.get('reason', '').strip()
        
        if not points or points == 0:
            flash('Points amount is required and cannot be zero.', 'error')
            return render_template('admin/add_points.html', member=member)
        
        if not reason:
            flash('Reason for points transaction is required.', 'error')
            return render_template('admin/add_points.html', member=member)
        
        # Get current points before transaction
        old_points = member.get_total_points()
        
        # Create transaction
        transaction = RewardTransaction(
            member_id=member.id,
            points=points,
            transaction_type=transaction_type,
            reason=reason,
            admin_id=current_user.id
        )
        db.session.add(transaction)
        
        # Check for new trophy achievements
        new_points = old_points + points
        check_and_award_trophies(member, old_points, new_points)
        
        db.session.commit()
        
        action = 'awarded to' if points > 0 else 'deducted from'
        flash(f'{abs(points)} points {action} {member.full_name}!', 'success')
        return redirect(url_for('admin.member_detail', member_id=member.id))
    
    return render_template('admin/add_points.html', member=member)


@admin_bp.route('/rewards/history')
@login_required
@admin_required
def rewards_history():
    """View all reward transactions"""
    # Get filter parameters
    member_id = request.args.get('member_id', type=int)
    transaction_type = request.args.get('type', '')
    
    query = RewardTransaction.query
    
    if member_id:
        query = query.filter_by(member_id=member_id)
    if transaction_type:
        query = query.filter_by(transaction_type=transaction_type)
    
    transactions = query.order_by(RewardTransaction.created_at.desc()).all()
    
    # Get all members for filter dropdown
    members = Member.query.join(User).filter(User.is_approved == True).order_by(Member.full_name.asc()).all()
    
    return render_template('admin/rewards_history.html',
                         transactions=transactions,
                         members=members,
                         current_member_id=member_id,
                         current_type=transaction_type)


@admin_bp.route('/rewards/trophies')
@login_required
@admin_required
def trophies():
    """Manage trophy definitions"""
    trophies = Trophy.query.order_by(Trophy.display_order.asc()).all()
    return render_template('admin/trophies.html', trophies=trophies)


@admin_bp.route('/rewards/trophies/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_trophy():
    """Add a new trophy"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        points_required = request.form.get('points_required', type=int)
        icon = request.form.get('icon')
        display_order = request.form.get('display_order', type=int, default=0)
        
        if not name or not points_required:
            flash('Trophy name and points required are mandatory.', 'error')
            return render_template('admin/add_trophy.html')
        
        # Check if trophy exists
        existing = Trophy.query.filter_by(name=name).first()
        if existing:
            flash('A trophy with this name already exists.', 'warning')
            return render_template('admin/add_trophy.html')
        
        trophy = Trophy(
            name=name,
            description=description,
            points_required=points_required,
            icon=icon,
            display_order=display_order
        )
        
        db.session.add(trophy)
        db.session.commit()
        
        flash(f'Trophy "{name}" created successfully!', 'success')
        return redirect(url_for('admin.trophies'))
    
    return render_template('admin/add_trophy.html')


@admin_bp.route('/rewards/trophies/edit/<int:trophy_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_trophy(trophy_id):
    """Edit an existing trophy"""
    trophy = Trophy.query.get_or_404(trophy_id)
    
    if request.method == 'POST':
        trophy.name = request.form.get('name')
        trophy.description = request.form.get('description')
        trophy.points_required = request.form.get('points_required', type=int)
        trophy.icon = request.form.get('icon')
        trophy.display_order = request.form.get('display_order', type=int, default=0)
        trophy.is_active = 'is_active' in request.form
        
        db.session.commit()
        
        flash(f'Trophy "{trophy.name}" updated successfully!', 'success')
        return redirect(url_for('admin.trophies'))
    
    return render_template('admin/edit_trophy.html', trophy=trophy)


@admin_bp.route('/rewards/trophies/delete/<int:trophy_id>')
@login_required
@admin_required
def delete_trophy(trophy_id):
    """Delete a trophy"""
    trophy = Trophy.query.get_or_404(trophy_id)
    name = trophy.name
    
    db.session.delete(trophy)
    db.session.commit()
    
    flash(f'Trophy "{name}" deleted successfully.', 'success')
    return redirect(url_for('admin.trophies'))


def check_and_award_trophies(member, old_points, new_points):
    """Check if member has earned any new trophies and award them"""
    # Get all active trophies
    all_trophies = Trophy.query.filter_by(is_active=True).order_by(Trophy.points_required.asc()).all()
    
    # Get already earned trophy IDs
    earned_trophy_ids = [mt.trophy_id for mt in member.member_trophies.all()]
    
    # Check each trophy
    for trophy in all_trophies:
        # Skip if already earned
        if trophy.id in earned_trophy_ids:
            continue
        
        # Check if member now qualifies
        if new_points >= trophy.points_required and old_points < trophy.points_required:
            # Award the trophy!
            member_trophy = MemberTrophy(
                member_id=member.id,
                trophy_id=trophy.id
            )
            db.session.add(member_trophy)
            flash(f'🎉 {member.full_name} earned a new trophy: {trophy.name}!', 'success')


# ============================================================================
# MEMBERSHIP PAYMENT ROUTES
# ============================================================================

@admin_bp.route('/payments')
@login_required
@admin_required
def payments():
    """View all membership payments"""
    status_filter = request.args.get('status', 'all')  # all, active, expired
    member_id = request.args.get('member_id', type=int)
    
    query = MembershipPayment.query
    
    if member_id:
        query = query.filter_by(member_id=member_id)
    
    payments = query.order_by(MembershipPayment.payment_date.desc()).all()
    
    # Filter by status
    if status_filter == 'active':
        payments = [p for p in payments if p.is_active()]
    elif status_filter == 'expired':
        payments = [p for p in payments if p.is_expired()]
    
    # Get all members for filter
    members = Member.query.join(User).filter(User.is_approved == True).order_by(Member.full_name.asc()).all()
    
    # Statistics
    total_payments = MembershipPayment.query.count()
    active_payments = sum(1 for p in MembershipPayment.query.all() if p.is_active())
    total_revenue = db.session.query(db.func.sum(MembershipPayment.amount)).scalar() or 0
    unassigned_payments_count = MembershipPayment.query.filter(
        MembershipPayment.financial_period_id.is_(None)
    ).count()
    
    # Get current financial period
    current_period = FinancialPeriod.query.filter_by(status='open').first()
    
    return render_template('admin/payments.html',
                         payments=payments,
                         members=members,
                         current_status=status_filter,
                         current_member_id=member_id,
                         total_payments=total_payments,
                         active_payments=active_payments,
                         total_revenue=total_revenue,
                         unassigned_payments_count=unassigned_payments_count,
                         current_period=current_period)


@admin_bp.route('/payments/add/<int:member_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def add_payment(member_id):
    """Record a new membership payment"""
    member = Member.query.get_or_404(member_id)
    
    # Get default settings
    default_fee = float(SystemSettings.get_setting('membership_fee', '50.00'))
    default_months = int(SystemSettings.get_setting('membership_duration_months', '12'))
    
    if request.method == 'POST':
        amount = request.form.get('amount', type=float)
        payment_date_str = request.form.get('payment_date')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        payment_method = request.form.get('payment_method', 'cash')
        notes = request.form.get('notes', '').strip()
        
        if not amount or not payment_date_str or not start_date_str or not end_date_str:
            flash('All date fields and amount are required.', 'error')
            return render_template('admin/add_payment.html', member=member, default_fee=default_fee)
        
        payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        if end_date <= start_date:
            flash('End date must be after start date.', 'error')
            return render_template('admin/add_payment.html', member=member, default_fee=default_fee)
        
        # Get current financial period
        current_period = FinancialPeriod.query.filter_by(status='open').first()
        
        payment = MembershipPayment(
            member_id=member.id,
            amount=amount,
            payment_date=payment_date,
            start_date=start_date,
            end_date=end_date,
            payment_method=payment_method,
            notes=notes,
            recorded_by=current_user.id,
            financial_period_id=current_period.id if current_period else None
        )
        
        db.session.add(payment)
        
        # Create financial transaction if there's an active period
        if current_period:
            # Get membership fees category
            membership_category = FinancialCategory.query.filter_by(name='Membership Fees', type='revenue').first()
            if membership_category:
                transaction = FinancialTransaction(
                    financial_period_id=current_period.id,
                    category_id=membership_category.id,
                    transaction_type='revenue',
                    amount=amount,
                    transaction_date=payment_date,
                    description=f"Membership fee payment from {member.full_name}",
                    notes=f"Payment method: {payment_method or 'Not specified'}",
                    reference_type='payment',
                    reference_id=payment.id,
                    recorded_by=current_user.id
                )
                db.session.add(transaction)
        
        db.session.commit()
        
        flash(f'Payment recorded successfully for {member.full_name}!', 'success')
        return redirect(url_for('admin.member_detail', member_id=member.id))
    
    # Calculate suggested end date
    today = datetime.utcnow().date()
    suggested_end = today + timedelta(days=default_months * 30)
    
    return render_template('admin/add_payment.html',
                         member=member,
                         default_fee=default_fee,
                         today=today,
                         suggested_end=suggested_end)


@admin_bp.route('/payments/edit/<int:payment_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_payment(payment_id):
    """Edit an existing payment record"""
    payment = MembershipPayment.query.get_or_404(payment_id)
    
    if request.method == 'POST':
        payment.amount = request.form.get('amount', type=float)
        payment.payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        payment.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        payment.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        payment.payment_method = request.form.get('payment_method', 'cash')
        payment.notes = request.form.get('notes', '').strip()
        
        db.session.commit()
        
        flash('Payment record updated successfully!', 'success')
        return redirect(url_for('admin.payments'))
    
    return render_template('admin/edit_payment.html', payment=payment)


@admin_bp.route('/payments/delete/<int:payment_id>')
@login_required
@admin_required
def delete_payment(payment_id):
    """Delete a payment record"""
    payment = MembershipPayment.query.get_or_404(payment_id)
    member_name = payment.member.full_name
    
    db.session.delete(payment)
    db.session.commit()
    
    flash(f'Payment record for {member_name} deleted successfully.', 'success')
    return redirect(url_for('admin.payments'))


@admin_bp.route('/payments/export')
@login_required
@admin_required
def export_payments():
    """Export payment records to CSV"""
    # Get filter parameters from query string
    status_filter = request.args.get('status', 'all')
    member_id = request.args.get('member_id', type=int)
    
    # Build query
    query = MembershipPayment.query
    
    if member_id:
        query = query.filter_by(member_id=member_id)
    
    payments = query.order_by(MembershipPayment.payment_date.desc()).all()
    
    # Apply status filter
    if status_filter == 'active':
        payments = [p for p in payments if p.is_active()]
    elif status_filter == 'expired':
        payments = [p for p in payments if p.is_expired()]
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Payment ID',
        'Member ID Number',
        'Member Name',
        'Member Email',
        'Amount (Tsh)',
        'Payment Date',
        'Start Date',
        'End Date',
        'Duration (Months)',
        'Payment Method',
        'Status',
        'Days Remaining',
        'Notes',
        'Created At'
    ])
    
    # Write data rows
    for payment in payments:
        # Calculate status
        if payment.is_active():
            status = 'Active'
            days_remaining = (payment.end_date - datetime.utcnow().date()).days
        elif payment.is_expired():
            status = 'Expired'
            days_remaining = (payment.end_date - datetime.utcnow().date()).days  # Will be negative
        else:
            status = 'Future'
            days_remaining = (payment.start_date - datetime.utcnow().date()).days
        
        # Calculate duration in months (approximate)
        duration_days = (payment.end_date - payment.start_date).days
        duration_months = round(duration_days / 30.44, 1)  # Average days per month
        
        writer.writerow([
            payment.id,
            payment.member.member_id_number,
            payment.member.full_name,
            payment.member.user.email,
            f"{payment.amount:.2f}",
            payment.payment_date.strftime('%Y-%m-%d'),
            payment.start_date.strftime('%Y-%m-%d'),
            payment.end_date.strftime('%Y-%m-%d'),
            duration_months,
            payment.payment_method,
            status,
            days_remaining,
            payment.notes or '',
            payment.created_at.strftime('%Y-%m-%d %H:%M:%S') if payment.created_at else ''
        ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=payments_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """System settings page"""
    if request.method == 'POST':
        # Update membership fee
        membership_fee = request.form.get('membership_fee')
        membership_duration = request.form.get('membership_duration_months')
        default_event_points = request.form.get('default_event_points')
        
        if membership_fee:
            SystemSettings.set_setting('membership_fee', membership_fee, 
                                      'Default membership fee amount', current_user.id)
        
        if membership_duration:
            SystemSettings.set_setting('membership_duration_months', membership_duration,
                                      'Default membership duration in months', current_user.id)
        
        if default_event_points:
            SystemSettings.set_setting('default_event_points', default_event_points,
                                      'Default points for event attendance', current_user.id)
        
        db.session.commit()
        
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin.settings'))
    
    # Get current settings
    membership_fee = SystemSettings.get_setting('membership_fee', '50.00')
    membership_duration = SystemSettings.get_setting('membership_duration_months', '12')
    default_event_points = SystemSettings.get_setting('default_event_points', '100')
    
    return render_template('admin/settings.html',
                         membership_fee=membership_fee,
                         membership_duration=membership_duration,
                         default_event_points=default_event_points)


# ============================================================================
# EVENT CHECK-IN ROUTES
# ============================================================================

@admin_bp.route('/events/<int:event_id>/checkin')
@login_required
@admin_required
def event_checkin(event_id):
    """Event check-in page"""
    event = Event.query.get_or_404(event_id)
    
    if not event.allows_check_in:
        flash('Check-in is not enabled for this event.', 'warning')
        return redirect(url_for('admin.events'))
    
    # Get all approved RSVPs for this event
    rsvps = RSVP.query.filter_by(event_id=event.id, status='approved').order_by(RSVP.full_name.asc()).all()
    
    # Statistics
    total_rsvps = len(rsvps)
    checked_in = sum(1 for r in rsvps if r.checked_in)
    not_checked_in = total_rsvps - checked_in
    
    return render_template('admin/event_checkin.html',
                         event=event,
                         rsvps=rsvps,
                         total_rsvps=total_rsvps,
                         checked_in=checked_in,
                         not_checked_in=not_checked_in)


@admin_bp.route('/rsvps/checkin/<int:rsvp_id>', methods=['POST'])
@login_required
@admin_required
def checkin_rsvp(rsvp_id):
    """Mark RSVP as checked in"""
    rsvp = RSVP.query.get_or_404(rsvp_id)
    
    if rsvp.checked_in:
        return jsonify({'success': False, 'error': 'Already checked in'})
    
    # Mark as checked in
    rsvp.checked_in = True
    rsvp.checked_in_at = datetime.utcnow()
    rsvp.checked_in_by = current_user.id
    
    # Award points if member and event has points
    if rsvp.member_id and rsvp.event.check_in_points > 0:
        member = rsvp.member
        old_points = member.get_total_points()
        
        transaction = RewardTransaction(
            member_id=member.id,
            points=rsvp.event.check_in_points,
            transaction_type='event_checkin',
            reason=f'Attended: {rsvp.event.title}',
            event_id=rsvp.event.id,
            admin_id=current_user.id
        )
        db.session.add(transaction)
        
        # Check for trophies
        new_points = old_points + rsvp.event.check_in_points
        check_and_award_trophies(member, old_points, new_points)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{rsvp.full_name} checked in successfully',
        'points_awarded': rsvp.event.check_in_points if rsvp.member_id else 0
    })


@admin_bp.route('/rsvps/checkin/<int:rsvp_id>/undo', methods=['POST'])
@login_required
@admin_required
def undo_checkin(rsvp_id):
    """Undo check-in for an RSVP"""
    rsvp = RSVP.query.get_or_404(rsvp_id)
    
    if not rsvp.checked_in:
        return jsonify({'success': False, 'error': 'Not checked in'})
    
    # Undo check-in
    rsvp.checked_in = False
    rsvp.checked_in_at = None
    rsvp.checked_in_by = None
    
    # Remove points if they were awarded
    if rsvp.member_id and rsvp.event.check_in_points > 0:
        # Find and remove the transaction
        transaction = RewardTransaction.query.filter_by(
            member_id=rsvp.member_id,
            event_id=rsvp.event.id,
            transaction_type='event_checkin'
        ).first()
        
        if transaction:
            db.session.delete(transaction)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Check-in undone for {rsvp.full_name}'
    })


# ============================================================================
# FINANCIAL MANAGEMENT ROUTES
# ============================================================================

@admin_bp.route('/financial')
@login_required
@admin_required
def financial():
    """Main financial management page"""
    # Get all financial periods
    periods = FinancialPeriod.query.order_by(FinancialPeriod.start_date.desc()).all()
    
    # Get current open period
    current_period = FinancialPeriod.query.filter_by(status='open').first()
    
    # Get statistics
    total_periods = FinancialPeriod.query.count()
    open_periods = FinancialPeriod.query.filter_by(status='open').count()
    closed_periods = FinancialPeriod.query.filter_by(status='closed').count()
    
    # Calculate all-time totals
    all_time_revenue = db.session.query(db.func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.transaction_type == 'revenue'
    ).scalar() or 0
    
    all_time_expenses = db.session.query(db.func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.transaction_type == 'expense'
    ).scalar() or 0
    
    all_time_balance = all_time_revenue - all_time_expenses

    membership_payments_total = db.session.query(db.func.sum(MembershipPayment.amount)).scalar() or 0
    membership_payments_count = MembershipPayment.query.count()
    unassigned_payments_count = MembershipPayment.query.filter(
        MembershipPayment.financial_period_id.is_(None)
    ).count()
    current_period_payments_total = 0
    if current_period:
        current_period_payments_total = db.session.query(db.func.sum(MembershipPayment.amount)).filter(
            MembershipPayment.financial_period_id == current_period.id
        ).scalar() or 0
    
    return render_template('admin/financial.html',
                         periods=periods,
                         current_period=current_period,
                         total_periods=total_periods,
                         open_periods=open_periods,
                         closed_periods=closed_periods,
                         all_time_revenue=all_time_revenue,
                         all_time_expenses=all_time_expenses,
                         all_time_balance=all_time_balance,
                         membership_payments_total=membership_payments_total,
                         membership_payments_count=membership_payments_count,
                         unassigned_payments_count=unassigned_payments_count,
                         current_period_payments_total=current_period_payments_total)


@admin_bp.route('/financial/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_financial_period():
    """Create and open a new financial period"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        description = request.form.get('description', '').strip()
        close_previous = 'close_previous' in request.form
        
        if not name or not start_date_str or not end_date_str:
            flash('All required fields must be filled.', 'error')
            return render_template('admin/add_financial_period.html')
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return render_template('admin/add_financial_period.html')
        
        if end_date <= start_date:
            flash('End date must be after start date.', 'error')
            return render_template('admin/add_financial_period.html')
        
        # Check if there's already an open period
        existing_open = FinancialPeriod.query.filter_by(status='open').first()
        if existing_open and not close_previous:
            flash('There is already an open financial period. Please close it first or check "Close Previous Period".', 'error')
            return render_template('admin/add_financial_period.html')
        
        # Close previous period if requested
        if close_previous and existing_open:
            existing_open.status = 'closed'
            existing_open.closed_by = current_user.id
            existing_open.closed_at = datetime.utcnow()
        
        # Create new period
        new_period = FinancialPeriod(
            name=name,
            start_date=start_date,
            end_date=end_date,
            description=description,
            opened_by=current_user.id
        )
        
        db.session.add(new_period)
        db.session.commit()
        
        flash(f'Financial period "{name}" created and opened successfully!', 'success')
        return redirect(url_for('admin.financial_period_detail', period_id=new_period.id))
    
    # Check for existing open period
    existing_open = FinancialPeriod.query.filter_by(status='open').first()
    
    return render_template('admin/add_financial_period.html', existing_open=existing_open)


@admin_bp.route('/financial/<int:period_id>')
@login_required
@admin_required
def financial_period_detail(period_id):
    """View financial period details and transactions"""
    period = FinancialPeriod.query.get_or_404(period_id)
    
    # Get filter parameters
    transaction_type = request.args.get('type', '')
    category_id = request.args.get('category_id', type=int)
    
    # Build query for transactions
    query = period.transactions
    
    if transaction_type:
        query = query.filter_by(transaction_type=transaction_type)
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    transactions = query.order_by(FinancialTransaction.transaction_date.desc()).all()
    
    # Get categories for filter
    categories = FinancialCategory.query.filter_by(is_active=True).order_by(
        FinancialCategory.type.asc(), FinancialCategory.name.asc()
    ).all()
    
    # Calculate statistics
    total_revenue = period.get_total_revenue()
    total_expenses = period.get_total_expenses()
    net_balance = period.get_net_balance()
    transaction_count = period.get_transaction_count()
    
    # Get category breakdown
    category_breakdown = db.session.query(
        FinancialCategory.name,
        FinancialCategory.type,
        db.func.sum(FinancialTransaction.amount).label('total')
    ).join(FinancialTransaction).filter(
        FinancialTransaction.financial_period_id == period.id
    ).group_by(FinancialCategory.id, FinancialCategory.name, FinancialCategory.type).all()
    
    return render_template('admin/financial_period_detail.html',
                         period=period,
                         transactions=transactions,
                         categories=categories,
                         total_revenue=total_revenue,
                         total_expenses=total_expenses,
                         net_balance=net_balance,
                         transaction_count=transaction_count,
                         category_breakdown=category_breakdown,
                         current_type=transaction_type,
                         current_category_id=category_id)


@admin_bp.route('/financial/<int:period_id>/close', methods=['POST'])
@login_required
@admin_required
def close_financial_period(period_id):
    """Close a financial period"""
    period = FinancialPeriod.query.get_or_404(period_id)
    
    if period.status == 'closed':
        flash('This period is already closed.', 'warning')
        return redirect(url_for('admin.financial_period_detail', period_id=period_id))
    
    period.status = 'closed'
    period.closed_by = current_user.id
    period.closed_at = datetime.utcnow()
    
    db.session.commit()
    
    flash(f'Financial period "{period.name}" has been closed successfully.', 'success')
    return redirect(url_for('admin.financial_period_detail', period_id=period_id))


@admin_bp.route('/financial/<int:period_id>/reopen', methods=['POST'])
@login_required
@admin_required
def reopen_financial_period(period_id):
    """Reopen a closed financial period (admin only)"""
    period = FinancialPeriod.query.get_or_404(period_id)
    
    if period.status == 'open':
        flash('This period is already open.', 'warning')
        return redirect(url_for('admin.financial_period_detail', period_id=period_id))
    
    # Check if there's already an open period
    existing_open = FinancialPeriod.query.filter_by(status='open').first()
    if existing_open:
        flash('There is already an open financial period. Please close it first.', 'error')
        return redirect(url_for('admin.financial_period_detail', period_id=period_id))
    
    period.status = 'open'
    period.closed_by = None
    period.closed_at = None
    
    db.session.commit()
    
    flash(f'Financial period "{period.name}" has been reopened successfully.', 'success')
    return redirect(url_for('admin.financial_period_detail', period_id=period_id))


@admin_bp.route('/financial/<int:period_id>/add-transaction', methods=['GET', 'POST'])
@login_required
@admin_required
def add_transaction(period_id):
    """Add a new financial transaction"""
    period = FinancialPeriod.query.get_or_404(period_id)
    
    if period.status == 'closed':
        flash('Cannot add transactions to a closed period.', 'error')
        return redirect(url_for('admin.financial_period_detail', period_id=period_id))
    
    if request.method == 'POST':
        transaction_type = request.form.get('transaction_type')
        category_id = request.form.get('category_id', type=int)
        amount = request.form.get('amount', type=float)
        transaction_date_str = request.form.get('transaction_date')
        description = request.form.get('description', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not all([transaction_type, category_id, amount, transaction_date_str, description]):
            flash('All required fields must be filled.', 'error')
            return render_template('admin/add_transaction.html', period=period, categories=categories)
        
        if amount <= 0:
            flash('Amount must be greater than zero.', 'error')
            return render_template('admin/add_transaction.html', period=period, categories=categories)
        
        try:
            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return render_template('admin/add_transaction.html', period=period, categories=categories)
        
        # Verify category exists and matches transaction type
        category = FinancialCategory.query.get(category_id)
        if not category or category.type != transaction_type:
            flash('Invalid category for transaction type.', 'error')
            return render_template('admin/add_transaction.html', period=period, categories=categories)
        
        transaction = FinancialTransaction(
            financial_period_id=period.id,
            category_id=category_id,
            transaction_type=transaction_type,
            amount=amount,
            transaction_date=transaction_date,
            description=description,
            notes=notes,
            recorded_by=current_user.id
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        flash(f'Transaction "{description}" added successfully!', 'success')
        return redirect(url_for('admin.financial_period_detail', period_id=period_id))
    
    # Get categories filtered by transaction type (will be filtered by JavaScript)
    categories = FinancialCategory.query.filter_by(is_active=True).order_by(
        FinancialCategory.type.asc(), FinancialCategory.name.asc()
    ).all()
    
    return render_template('admin/add_transaction.html', period=period, categories=categories)


@admin_bp.route('/financial/transactions/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_transaction(transaction_id):
    """Edit a financial transaction"""
    transaction = FinancialTransaction.query.get_or_404(transaction_id)
    
    if transaction.financial_period.status == 'closed':
        flash('Cannot edit transactions in a closed period.', 'error')
        return redirect(url_for('admin.financial_period_detail', period_id=transaction.financial_period_id))
    
    if request.method == 'POST':
        transaction_type = request.form.get('transaction_type')
        category_id = request.form.get('category_id', type=int)
        amount = request.form.get('amount', type=float)
        transaction_date_str = request.form.get('transaction_date')
        description = request.form.get('description', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not all([transaction_type, category_id, amount, transaction_date_str, description]):
            flash('All required fields must be filled.', 'error')
            return render_template('admin/edit_transaction.html', transaction=transaction, categories=categories)
        
        if amount <= 0:
            flash('Amount must be greater than zero.', 'error')
            return render_template('admin/edit_transaction.html', transaction=transaction, categories=categories)
        
        try:
            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return render_template('admin/edit_transaction.html', transaction=transaction, categories=categories)
        
        # Verify category exists and matches transaction type
        category = FinancialCategory.query.get(category_id)
        if not category or category.type != transaction_type:
            flash('Invalid category for transaction type.', 'error')
            return render_template('admin/edit_transaction.html', transaction=transaction, categories=categories)
        
        transaction.transaction_type = transaction_type
        transaction.category_id = category_id
        transaction.amount = amount
        transaction.transaction_date = transaction_date
        transaction.description = description
        transaction.notes = notes
        
        db.session.commit()
        
        flash(f'Transaction "{description}" updated successfully!', 'success')
        return redirect(url_for('admin.financial_period_detail', period_id=transaction.financial_period_id))
    
    # Get categories filtered by transaction type
    categories = FinancialCategory.query.filter_by(is_active=True).order_by(
        FinancialCategory.type.asc(), FinancialCategory.name.asc()
    ).all()
    
    return render_template('admin/edit_transaction.html', transaction=transaction, categories=categories)


@admin_bp.route('/financial/transactions/<int:transaction_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_transaction(transaction_id):
    """Delete a financial transaction"""
    transaction = FinancialTransaction.query.get_or_404(transaction_id)
    
    if transaction.financial_period.status == 'closed':
        flash('Cannot delete transactions in a closed period.', 'error')
        return redirect(url_for('admin.financial_period_detail', period_id=transaction.financial_period_id))
    
    description = transaction.description
    period_id = transaction.financial_period_id
    
    db.session.delete(transaction)
    db.session.commit()
    
    flash(f'Transaction "{description}" deleted successfully.', 'success')
    return redirect(url_for('admin.financial_period_detail', period_id=period_id))


@admin_bp.route('/financial/categories')
@login_required
@admin_required
def financial_categories():
    """Manage financial categories"""
    categories = FinancialCategory.query.order_by(
        FinancialCategory.type.asc(), FinancialCategory.name.asc()
    ).all()
    
    return render_template('admin/financial_categories.html', categories=categories)


@admin_bp.route('/financial/categories/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_financial_category():
    """Add a new financial category"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_type = request.form.get('type')
        description = request.form.get('description', '').strip()
        
        if not name or not category_type:
            flash('Name and type are required.', 'error')
            return render_template('admin/add_financial_category.html')
        
        # Check if category already exists
        existing = FinancialCategory.query.filter_by(name=name, type=category_type).first()
        if existing:
            flash('A category with this name and type already exists.', 'warning')
            return render_template('admin/add_financial_category.html')
        
        category = FinancialCategory(
            name=name,
            type=category_type,
            description=description,
            is_builtin=False,
            is_active=True
        )
        
        db.session.add(category)
        db.session.commit()
        
        flash(f'Category "{name}" added successfully!', 'success')
        return redirect(url_for('admin.financial_categories'))
    
    return render_template('admin/add_financial_category.html')


@admin_bp.route('/financial/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_financial_category(category_id):
    """Edit a financial category"""
    category = FinancialCategory.query.get_or_404(category_id)
    
    if category.is_builtin:
        flash('Built-in categories cannot be edited.', 'error')
        return redirect(url_for('admin.financial_categories'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Name is required.', 'error')
            return render_template('admin/edit_financial_category.html', category=category)
        
        # Check if another category with same name and type exists
        existing = FinancialCategory.query.filter(
            FinancialCategory.name == name,
            FinancialCategory.type == category.type,
            FinancialCategory.id != category.id
        ).first()
        
        if existing:
            flash('A category with this name and type already exists.', 'warning')
            return render_template('admin/edit_financial_category.html', category=category)
        
        category.name = name
        category.description = description
        
        db.session.commit()
        
        flash(f'Category "{name}" updated successfully!', 'success')
        return redirect(url_for('admin.financial_categories'))
    
    return render_template('admin/edit_financial_category.html', category=category)


@admin_bp.route('/financial/categories/<int:category_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_financial_category(category_id):
    """Toggle category active status"""
    category = FinancialCategory.query.get_or_404(category_id)
    
    if category.is_builtin:
        flash('Built-in categories cannot be deactivated.', 'error')
        return redirect(url_for('admin.financial_categories'))
    
    category.is_active = not category.is_active
    db.session.commit()
    
    status = 'activated' if category.is_active else 'deactivated'
    flash(f'Category "{category.name}" {status} successfully.', 'success')
    return redirect(url_for('admin.financial_categories'))


@admin_bp.route('/financial/reports')
@login_required
@admin_required
def financial_reports():
    """Comprehensive financial reports"""
    # Get all periods
    periods = FinancialPeriod.query.order_by(FinancialPeriod.start_date.desc()).all()
    
    # Calculate all-time totals
    all_time_revenue = db.session.query(db.func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.transaction_type == 'revenue'
    ).scalar() or 0
    
    all_time_expenses = db.session.query(db.func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.transaction_type == 'expense'
    ).scalar() or 0
    
    all_time_balance = all_time_revenue - all_time_expenses
    
    # Get category totals across all periods
    category_totals = db.session.query(
        FinancialCategory.name,
        FinancialCategory.type,
        db.func.sum(FinancialTransaction.amount).label('total')
    ).join(FinancialTransaction).group_by(
        FinancialCategory.id, FinancialCategory.name, FinancialCategory.type
    ).order_by(db.func.sum(FinancialTransaction.amount).desc()).all()
    
    return render_template('admin/financial_reports.html',
                         periods=periods,
                         all_time_revenue=all_time_revenue,
                         all_time_expenses=all_time_expenses,
                         all_time_balance=all_time_balance,
                         category_totals=category_totals)


@admin_bp.route('/financial/export/<int:period_id>')
@login_required
@admin_required
def export_financial_period(period_id):
    """Export financial period report as CSV"""
    period = FinancialPeriod.query.get_or_404(period_id)
    
    try:
        from flask import Response
        import csv
        import io
        
        # Get all transactions for the period
        transactions = period.transactions.order_by(FinancialTransaction.transaction_date.desc()).all()
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Date', 'Type', 'Category', 'Description', 'Amount', 'Notes', 'Recorded By'
        ])
        
        # Write data
        for transaction in transactions:
            writer.writerow([
                transaction.transaction_date.strftime('%Y-%m-%d'),
                transaction.transaction_type.title(),
                transaction.category.name,
                transaction.description,
                f"Tsh {transaction.amount:.2f}",
                transaction.notes or '',
                transaction.recorder.email
            ])
        
        # Add summary
        writer.writerow([])
        writer.writerow(['SUMMARY'])
        writer.writerow(['Total Revenue', f"Tsh {period.get_total_revenue():.2f}"])
        writer.writerow(['Total Expenses', f"Tsh {period.get_total_expenses():.2f}"])
        writer.writerow(['Net Balance', f"Tsh {period.get_net_balance():.2f}"])
        
        # Prepare response
        output.seek(0)
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=financial_report_{period.name.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
        
        return response
        
    except Exception as e:
        flash(f'Error exporting report: {str(e)}', 'error')
        return redirect(url_for('admin.financial_period_detail', period_id=period_id))

# Competitions

def _competition_is_judge(competition_id, user_id):
    return CompetitionJudge.query.filter_by(competition_id=competition_id, user_id=user_id, is_active=True).first()


def _calculate_submission_scores(submission):
    competition = submission.competition
    criteria = competition.criteria.order_by(CompetitionCriteria.id.asc()).all()
    criteria_total = sum(c.weight_percent or 0 for c in criteria)
    judges = competition.judges.filter_by(is_active=True).all()

    judge_totals = []
    for judge in judges:
        total = 0
        scored_any = False
        for c in criteria:
            score_row = CompetitionScore.query.filter_by(
                submission_id=submission.id,
                judge_id=judge.user_id,
                criteria_id=c.id
            ).first()
            if score_row:
                scored_any = True
                max_points = c.max_points or 1
                total += (score_row.score / max_points) * (c.weight_percent or 0)
        if scored_any:
            judge_totals.append(total)

    submission.total_score = round(sum(judge_totals) / len(judge_totals), 2) if judge_totals else 0
    submission.final_score = round(submission.total_score + (submission.bonus_points or 0), 2)


@admin_bp.route('/competitions')
@login_required
@admin_required
def competitions():
    items = Competition.query.order_by(Competition.created_at.desc()).all()
    return render_template('admin/competitions/index.html', competitions=items, view_label='All')


@admin_bp.route('/competitions/weekly')
@login_required
@admin_required
def competitions_weekly():
    items = Competition.query.filter_by(frequency='weekly').order_by(Competition.created_at.desc()).all()
    return render_template('admin/competitions/index.html', competitions=items, view_label='Weekly')


@admin_bp.route('/competitions/monthly')
@login_required
@admin_required
def competitions_monthly():
    items = Competition.query.filter_by(frequency='monthly').order_by(Competition.created_at.desc()).all()
    return render_template('admin/competitions/index.html', competitions=items, view_label='Monthly')


@admin_bp.route('/competitions/add', methods=['GET', 'POST'])
@login_required
@admin_required
def competitions_add():
    if request.method == 'POST':
        starts_at = datetime.strptime(request.form.get('starts_at'), '%Y-%m-%dT%H:%M') if request.form.get('starts_at') else None
        ends_at = datetime.strptime(request.form.get('ends_at'), '%Y-%m-%dT%H:%M') if request.form.get('ends_at') else None
        if not starts_at or not ends_at or ends_at <= starts_at:
            flash('End time must be after start time.', 'error')
            return redirect(url_for('admin.competitions_add'))

        competition = Competition(
            title=request.form.get('title'),
            description=request.form.get('description'),
            category=request.form.get('category'),
            frequency=request.form.get('frequency'),
            level=int(request.form.get('level') or 1),
            status=request.form.get('status', 'draft'),
            eligibility_rule=request.form.get('eligibility_rule', 'default'),
            eligibility_years=request.form.get('eligibility_years'),
            requires_paid_membership=bool(request.form.get('requires_paid_membership')),
            submission_type=request.form.get('submission_type'),
            submission_max_mb=int(request.form.get('submission_max_mb') or 10),
            starts_at=starts_at,
            ends_at=ends_at,
            assessment_mode=request.form.get('assessment_mode', 'online'),
            assessment_instructions=request.form.get('assessment_instructions'),
            assessment_link=request.form.get('assessment_link'),
            assessment_location=request.form.get('assessment_location'),
            assessment_date=datetime.strptime(request.form.get('assessment_date'), '%Y-%m-%dT%H:%M') if request.form.get('assessment_date') else None,
            created_by=current_user.id,
        )
        db.session.add(competition)
        db.session.commit()
        flash('Competition created. Add judges, criteria, and rewards next.', 'success')
        return redirect(url_for('admin.competitions_view', competition_id=competition.id))

    return render_template('admin/competitions/form.html', competition=None)


@admin_bp.route('/competitions/<int:competition_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def competitions_edit(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if request.method == 'POST':
        if competition.status == 'finalized':
            flash('Finalized competitions are locked and cannot be edited.', 'error')
            return redirect(url_for('admin.competitions_view', competition_id=competition.id))
        assessment_only = competition.status in ['published', 'judging']
        if assessment_only:
            new_status = request.form.get('status', competition.status)
            if new_status not in ['published', 'judging', 'cancelled']:
                flash('Only status changes to Published, Judging, or Cancelled are allowed here.', 'error')
                return redirect(url_for('admin.competitions_edit', competition_id=competition.id))
            competition.status = new_status
            competition.assessment_mode = request.form.get('assessment_mode', competition.assessment_mode)
            competition.assessment_instructions = request.form.get('assessment_instructions')
            competition.assessment_link = request.form.get('assessment_link')
            competition.assessment_location = request.form.get('assessment_location')
            competition.assessment_date = datetime.strptime(request.form.get('assessment_date'), '%Y-%m-%dT%H:%M') if request.form.get('assessment_date') else competition.assessment_date
            flash('Competition is active. Only status and assessment details were updated.', 'warning')
        else:
            starts_at = datetime.strptime(request.form.get('starts_at'), '%Y-%m-%dT%H:%M') if request.form.get('starts_at') else competition.starts_at
            ends_at = datetime.strptime(request.form.get('ends_at'), '%Y-%m-%dT%H:%M') if request.form.get('ends_at') else competition.ends_at
            if ends_at <= starts_at:
                flash('End time must be after start time.', 'error')
                return redirect(url_for('admin.competitions_edit', competition_id=competition.id))
            competition.title = request.form.get('title')
            competition.description = request.form.get('description')
            competition.category = request.form.get('category')
            competition.frequency = request.form.get('frequency')
            competition.level = int(request.form.get('level') or competition.level)
            competition.status = request.form.get('status', competition.status)
            competition.eligibility_rule = request.form.get('eligibility_rule', competition.eligibility_rule)
            competition.eligibility_years = request.form.get('eligibility_years')
            competition.requires_paid_membership = bool(request.form.get('requires_paid_membership'))
            competition.submission_type = request.form.get('submission_type')
            competition.submission_max_mb = int(request.form.get('submission_max_mb') or competition.submission_max_mb)
            competition.starts_at = starts_at
            competition.ends_at = ends_at
            competition.assessment_mode = request.form.get('assessment_mode', competition.assessment_mode)
            competition.assessment_instructions = request.form.get('assessment_instructions')
            competition.assessment_link = request.form.get('assessment_link')
            competition.assessment_location = request.form.get('assessment_location')
            competition.assessment_date = datetime.strptime(request.form.get('assessment_date'), '%Y-%m-%dT%H:%M') if request.form.get('assessment_date') else competition.assessment_date
        db.session.commit()
        flash('Competition updated.', 'success')
        return redirect(url_for('admin.competitions_view', competition_id=competition.id))

    assessment_only = competition.status in ['published', 'judging']
    finalized_locked = competition.status == 'finalized'
    return render_template('admin/competitions/form.html', competition=competition, assessment_only=assessment_only, finalized_locked=finalized_locked)


@admin_bp.route('/competitions/<int:competition_id>')
@login_required
@admin_required
def competitions_view(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    users = User.query.order_by(User.email.asc()).all()
    sponsors_all = CompetitionSponsor.query.filter_by(is_active=True).order_by(CompetitionSponsor.name.asc()).all()
    judges = competition.judges.filter_by(is_active=True).join(User).order_by(User.email.asc()).all()
    criteria = competition.criteria.order_by(CompetitionCriteria.id.asc()).all()
    criteria_total = sum(c.weight_percent or 0 for c in criteria)
    rewards = competition.rewards.order_by(CompetitionReward.id.asc()).all()
    sponsors = competition.sponsors.order_by(CompetitionSponsorLink.display_order.asc()).all()
    submissions_count = competition.submissions.count()
    enrollments_count = competition.enrollments.count()
    return render_template('admin/competitions/detail.html', competition=competition, judges=judges, criteria=criteria, rewards=rewards, sponsors=sponsors, submissions_count=submissions_count, enrollments_count=enrollments_count, users=users, sponsors_all=sponsors_all, criteria_total=criteria_total)


@admin_bp.route('/competitions/<int:competition_id>/criteria/add', methods=['POST'])
@login_required
@admin_required
def competitions_criteria_add(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    criteria = CompetitionCriteria(
        competition_id=competition.id,
        name=request.form.get('name'),
        description=request.form.get('description'),
        max_points=int(request.form.get('max_points') or 10),
        weight_percent=int(request.form.get('weight_percent') or 0),
    )
    db.session.add(criteria)
    db.session.commit()
    flash('Criteria added.', 'success')
    return redirect(url_for('admin.competitions_view', competition_id=competition.id))


@admin_bp.route('/competitions/<int:competition_id>/criteria/<int:criteria_id>/delete', methods=['POST'])
@login_required
@admin_required
def competitions_criteria_delete(competition_id, criteria_id):
    criteria = CompetitionCriteria.query.get_or_404(criteria_id)
    db.session.delete(criteria)
    db.session.commit()
    flash('Criteria removed.', 'success')
    return redirect(url_for('admin.competitions_view', competition_id=competition_id))


@admin_bp.route('/competitions/<int:competition_id>/judges', methods=['GET', 'POST'])
@login_required
@admin_required
def competitions_judges(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if request.method == 'POST':
        user_id = int(request.form.get('user_id'))
        is_chair = bool(request.form.get('is_chair'))
        user = User.query.get(user_id)
        if is_chair and (not user or user.role != 'admin'):
            flash('Chair judge must be an admin user.', 'error')
            return redirect(url_for('admin.competitions_view', competition_id=competition.id))
        existing = CompetitionJudge.query.filter_by(competition_id=competition.id, user_id=user_id).first()
        if not existing:
            db.session.add(CompetitionJudge(competition_id=competition.id, user_id=user_id, is_chair=is_chair))
        else:
            existing.is_active = True
            existing.is_chair = is_chair
        if is_chair:
            CompetitionJudge.query.filter(
                CompetitionJudge.competition_id == competition.id,
                CompetitionJudge.user_id != user_id
            ).update({CompetitionJudge.is_chair: False})
        db.session.commit()
        flash('Judge assigned.', 'success')
        return redirect(url_for('admin.competitions_view', competition_id=competition.id))
    
    return redirect(url_for('admin.competitions_view', competition_id=competition.id))


@admin_bp.route('/competitions/<int:competition_id>/judges/<int:judge_id>/remove', methods=['POST'])
@login_required
@admin_required
def competitions_judges_remove(competition_id, judge_id):
    judge = CompetitionJudge.query.get_or_404(judge_id)
    judge.is_active = False
    judge.is_chair = False
    db.session.commit()
    flash('Judge removed.', 'success')
    return redirect(url_for('admin.competitions_view', competition_id=competition_id))


@admin_bp.route('/competitions/<int:competition_id>/rewards/add', methods=['POST'])
@login_required
@admin_required
def competitions_rewards_add(competition_id):
    reward_type = request.form.get('reward_type', 'position')
    rank_from = int(request.form.get('rank_from') or 1)
    rank_to = int(request.form.get('rank_to') or 1)
    percent = int(request.form.get('percent') or 0)
    points = int(request.form.get('points') or 0)
    if reward_type == 'percent' and (percent <= 0 or percent > 100):
        flash('Percent reward must be between 1 and 100.', 'error')
        return redirect(url_for('admin.competitions_view', competition_id=competition_id))
    if reward_type == 'position' and (rank_from <= 0 or rank_to <= 0 or rank_from > rank_to):
        flash('Rank range is invalid.', 'error')
        return redirect(url_for('admin.competitions_view', competition_id=competition_id))

    reward = CompetitionReward(
        competition_id=competition_id,
        reward_type=reward_type,
        rank_from=rank_from,
        rank_to=rank_to,
        percent=percent,
        points=points,
        prize_title=request.form.get('prize_title'),
        prize_description=request.form.get('prize_description'),
    )
    db.session.add(reward)
    db.session.commit()
    flash('Reward rule added.', 'success')
    return redirect(url_for('admin.competitions_view', competition_id=competition_id))


@admin_bp.route('/competitions/<int:competition_id>/rewards/<int:reward_id>/delete', methods=['POST'])
@login_required
@admin_required
def competitions_rewards_delete(competition_id, reward_id):
    reward = CompetitionReward.query.get_or_404(reward_id)
    db.session.delete(reward)
    db.session.commit()
    flash('Reward rule removed.', 'success')
    return redirect(url_for('admin.competitions_view', competition_id=competition_id))


@admin_bp.route('/competitions/<int:competition_id>/sponsors', methods=['GET', 'POST'])
@login_required
@admin_required
def competitions_sponsors(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if request.method == 'POST':
        sponsor_id = int(request.form.get('sponsor_id'))
        is_primary = bool(request.form.get('is_primary'))
        existing = CompetitionSponsorLink.query.filter_by(competition_id=competition.id, sponsor_id=sponsor_id).first()
        if not existing:
            db.session.add(CompetitionSponsorLink(competition_id=competition.id, sponsor_id=sponsor_id, is_primary=is_primary))
        else:
            existing.is_primary = is_primary
        if is_primary:
            CompetitionSponsorLink.query.filter(
                CompetitionSponsorLink.competition_id == competition.id,
                CompetitionSponsorLink.sponsor_id != sponsor_id
            ).update({CompetitionSponsorLink.is_primary: False})
        db.session.commit()
        flash('Sponsor assigned.', 'success')
        return redirect(url_for('admin.competitions_view', competition_id=competition.id))
    
    return redirect(url_for('admin.competitions_view', competition_id=competition.id))


@admin_bp.route('/competitions/sponsors/add', methods=['POST'])
@login_required
@admin_required
def competitions_sponsors_add():
    sponsor = CompetitionSponsor(
        name=request.form.get('name'),
        website=request.form.get('website'),
        logo=request.form.get('logo'),
        description=request.form.get('description')
    )
    db.session.add(sponsor)
    db.session.commit()
    flash('Sponsor created.', 'success')
    return redirect(request.referrer or url_for('admin.competitions'))


@admin_bp.route('/competitions/<int:competition_id>/submissions')
@login_required
@admin_required
def competitions_submissions(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    submissions = competition.submissions.join(Member).order_by(CompetitionSubmission.submitted_at.desc()).all()
    judge = _competition_is_judge(competition.id, current_user.id)
    is_judge = judge is not None
    is_chair = judge.is_chair if judge else False
    return render_template('admin/competitions/submissions.html', competition=competition, submissions=submissions, is_judge=is_judge, is_chair=is_chair)


@admin_bp.route('/competitions/<int:competition_id>/submissions/<int:submission_id>/score', methods=['GET', 'POST'])
@login_required
def competitions_score(competition_id, submission_id):
    competition = Competition.query.get_or_404(competition_id)
    submission = CompetitionSubmission.query.get_or_404(submission_id)
    if submission.competition_id != competition.id:
        flash('Invalid submission for this competition.', 'error')
        return redirect(url_for('admin.competitions_submissions', competition_id=competition.id))
    if competition.status == 'finalized':
        flash('Competition is finalized. Scoring is locked.', 'error')
        return redirect(url_for('admin.competitions_submissions', competition_id=competition.id))
    judge = _competition_is_judge(competition.id, current_user.id)
    if not judge:
        flash('You are not assigned to judge this competition.', 'error')
        return redirect(url_for('admin.competitions_submissions', competition_id=competition.id))

    criteria = competition.criteria.order_by(CompetitionCriteria.id.asc()).all()
    if request.method == 'POST':
        for c in criteria:
            value = float(request.form.get(f'criteria_{c.id}') or 0)
            if value > c.max_points:
                value = c.max_points
            score_row = CompetitionScore.query.filter_by(
                submission_id=submission.id,
                judge_id=current_user.id,
                criteria_id=c.id
            ).first()
            if not score_row:
                score_row = CompetitionScore(
                    submission_id=submission.id,
                    judge_id=current_user.id,
                    criteria_id=c.id
                )
                db.session.add(score_row)
            score_row.score = value
            score_row.comment = request.form.get(f'comment_{c.id}')
        db.session.commit()
        _calculate_submission_scores(submission)
        db.session.commit()
        flash('Scores saved.', 'success')
        return redirect(url_for('admin.competitions_submissions', competition_id=competition.id))

    existing_scores = {s.criteria_id: s for s in submission.scores.filter_by(judge_id=current_user.id).all()}
    return render_template('admin/competitions/score.html', competition=competition, submission=submission, criteria=criteria, existing_scores=existing_scores)


@admin_bp.route('/competitions/<int:competition_id>/finalize', methods=['POST'])
@login_required
@admin_required
def competitions_finalize(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    chair = CompetitionJudge.query.filter_by(competition_id=competition.id, user_id=current_user.id, is_chair=True, is_active=True).first()
    if not chair:
        flash('Only the chair judge can finalize the competition.', 'error')
        return redirect(url_for('admin.competitions_view', competition_id=competition.id))
    if chair.judge.role != 'admin':
        flash('Chair judge must be an admin to finalize.', 'error')
        return redirect(url_for('admin.competitions_view', competition_id=competition.id))

    criteria_total = sum(c.weight_percent or 0 for c in competition.criteria.all())
    if criteria_total != 100:
        flash(f'Criteria weights must total 100%. Current total: {criteria_total}%.', 'error')
        return redirect(url_for('admin.competitions_view', competition_id=competition.id))

    # Reset previous winners
    CompetitionWinner.query.filter_by(competition_id=competition.id).delete()
    CompetitionGuard.query.filter_by(competition_id=competition.id).delete()
    RewardTransaction.query.filter(
        RewardTransaction.transaction_type == 'competition',
        RewardTransaction.reason.ilike(f"Competition {competition.id}%")
    ).delete(synchronize_session=False)

    submissions = competition.submissions.filter(CompetitionSubmission.status != 'disqualified').all()
    submissions = sorted(submissions, key=lambda s: s.final_score, reverse=True)
    for idx, submission in enumerate(submissions, start=1):
        submission.rank = idx
        submission.is_winner = False
        submission.points_awarded = 0
    prize_map = {}

    # Apply rewards
    total_submissions = len(submissions)
    for reward in competition.rewards.all():
        if reward.reward_type == 'percent' and reward.percent:
            if total_submissions == 0:
                continue
            count = max(1, int((reward.percent / 100.0) * total_submissions))
            for submission in submissions[:count]:
                submission.points_awarded = max(submission.points_awarded or 0, reward.points or 0)
                submission.is_winner = True
                prize_map[submission.id] = (reward.prize_title, reward.prize_description)
        else:
            start = reward.rank_from or 1
            end = reward.rank_to or start
            for submission in submissions:
                if submission.rank and start <= submission.rank <= end:
                    submission.points_awarded = max(submission.points_awarded or 0, reward.points or 0)
                    submission.is_winner = True
                    prize_map[submission.id] = (reward.prize_title, reward.prize_description)

    for submission in submissions:
        if submission.is_winner:
            prize_title, prize_description = prize_map.get(submission.id, (None, None))
            db.session.add(CompetitionWinner(
                competition_id=competition.id,
                member_id=submission.member_id,
                level=competition.level,
                rank=submission.rank,
                points_awarded=submission.points_awarded,
                prize_title=prize_title,
                prize_description=prize_description,
            ))
            if submission.points_awarded:
                db.session.add(RewardTransaction(
                    member_id=submission.member_id,
                    points=submission.points_awarded,
                    transaction_type='competition',
                    reason=f"Competition {competition.id} - {competition.title} (Rank {submission.rank})",
                    admin_id=current_user.id
                ))

    if submissions:
        top = submissions[0]
        today = datetime.now().date()
        db.session.add(CompetitionGuard(
            competition_id=competition.id,
            member_id=top.member_id,
            level=competition.level,
            week_start=today,
            week_end=today + timedelta(days=7),
            title=f"Guard of the Week - Level {competition.level}",
            work_link=top.submission_value if top.submission_type in ['github', 'link'] else None
        ))

    competition.status = 'finalized'
    db.session.commit()
    flash('Competition finalized and winners published.', 'success')
    return redirect(url_for('admin.competitions_view', competition_id=competition.id))


@admin_bp.route('/competitions/<int:competition_id>/submissions/<int:submission_id>/bonus', methods=['POST'])
@login_required
@admin_required
def competitions_bonus(competition_id, submission_id):
    competition = Competition.query.get_or_404(competition_id)
    chair = CompetitionJudge.query.filter_by(competition_id=competition.id, user_id=current_user.id, is_chair=True, is_active=True).first()
    if not chair:
        flash('Only the chair judge can adjust bonus points.', 'error')
        return redirect(url_for('admin.competitions_submissions', competition_id=competition.id))
    submission = CompetitionSubmission.query.get_or_404(submission_id)
    bonus = float(request.form.get('bonus_points') or 0)
    submission.bonus_points = bonus
    _calculate_submission_scores(submission)
    db.session.commit()
    flash('Bonus points updated.', 'success')
    return redirect(url_for('admin.competitions_submissions', competition_id=competition.id))

@admin_bp.route('/competitions/<int:competition_id>/enrollments')
@login_required
@admin_required
def competitions_enrollments(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    enrollments = CompetitionEnrollment.query.filter_by(competition_id=competition.id).join(Member).order_by(CompetitionEnrollment.enrolled_at.desc()).all()
    return render_template('admin/competitions/enrollments.html', competition=competition, enrollments=enrollments)


@admin_bp.route('/competitions/<int:competition_id>/enrollments/<int:enrollment_id>/disqualify', methods=['POST'])
@login_required
@admin_required
def competitions_disqualify(competition_id, enrollment_id):
    competition = Competition.query.get_or_404(competition_id)
    enrollment = CompetitionEnrollment.query.get_or_404(enrollment_id)
    if enrollment.competition_id != competition.id:
        flash('Invalid enrollment.', 'error')
        return redirect(url_for('admin.competitions_enrollments', competition_id=competition.id))
    reason = request.form.get('disqualified_reason')
    enrollment.status = 'disqualified'
    enrollment.disqualified_reason = reason
    enrollment.disqualified_by = current_user.id
    enrollment.disqualified_at = datetime.now()

    submission = CompetitionSubmission.query.filter_by(competition_id=competition.id, member_id=enrollment.member_id).first()
    if submission:
        submission.status = 'disqualified'
    db.session.commit()
    flash('Member disqualified.', 'success')
    return redirect(url_for('admin.competitions_enrollments', competition_id=competition.id))


def _build_reward_badges(rewards, total_submissions):
    badges = {}
    if total_submissions == 0:
        return badges
    for reward in rewards:
        if reward.reward_type == "percent" and reward.percent:
            count = max(1, int((reward.percent / 100.0) * total_submissions))
            for rank in range(1, count + 1):
                badges[rank] = (reward.points or 0, reward.prize_title, reward.prize_description, f"Top {reward.percent}%")
        else:
            start = reward.rank_from or 1
            end = reward.rank_to or start
            for rank in range(start, end + 1):
                badges[rank] = (reward.points or 0, reward.prize_title, reward.prize_description, f"Rank {start}-{end}")
    return badges


@admin_bp.route('/competitions/<int:competition_id>/leaderboard')
@login_required
@admin_required
def competitions_leaderboard(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    submissions_query = competition.submissions.filter(CompetitionSubmission.status != 'disqualified').order_by(CompetitionSubmission.final_score.desc())
    page = request.args.get('page', 1, type=int)
    submissions_page = submissions_query.paginate(page=page, per_page=20, error_out=False)
    rewards = competition.rewards.order_by(CompetitionReward.id.asc()).all()
    badges = _build_reward_badges(rewards, submissions_page.total)
    chair = CompetitionJudge.query.filter_by(competition_id=competition.id, user_id=current_user.id, is_chair=True, is_active=True).first()
    can_finalize = chair is not None and chair.judge.role == 'admin' and competition.status != 'finalized'
    return render_template('admin/competitions/leaderboard.html', competition=competition, submissions=submissions_page, badges=badges, can_finalize=can_finalize)


# Sessions
def _session_categories():
    return [
        'Web Development',
        'Mobile Development',
        'Cybersecurity',
        'DevOps',
        'Graphics Design',
        'Data Science',
        'AI/ML',
        'Networking',
        'Other',
    ]


@admin_bp.route('/sessions')
@login_required
@admin_required
def sessions_index():
    weeks = SessionWeek.query.order_by(SessionWeek.week_start.desc()).all()
    return render_template('admin/sessions/index.html', weeks=weeks)


@admin_bp.route('/sessions/week/add', methods=['GET', 'POST'])
@login_required
@admin_required
def sessions_week_add():
    if request.method == 'POST':
        title = request.form.get('title') or 'Weekly Sessions'
        week_start = request.form.get('week_start')
        if not week_start:
            flash('Week start date is required.', 'error')
            return redirect(url_for('admin.sessions_week_add'))
        try:
            week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid start date format.', 'error')
            return redirect(url_for('admin.sessions_week_add'))
        week_end_date = week_start_date + timedelta(days=6)
        week = SessionWeek(
            title=title,
            week_start=week_start_date,
            week_end=week_end_date,
            status='draft'
        )
        db.session.add(week)
        db.session.commit()
        flash('Session week created.', 'success')
        return redirect(url_for('admin.sessions_week_view', week_id=week.id))
    return render_template('admin/sessions/week_form.html')


@admin_bp.route('/sessions/week/<int:week_id>')
@login_required
@admin_required
def sessions_week_view(week_id):
    week = SessionWeek.query.get_or_404(week_id)
    sessions = week.sessions.order_by(SessionSchedule.session_date.asc(), SessionSchedule.start_time.asc()).all()
    day_map = {}
    for session in sessions:
        day_map.setdefault(session.session_date, []).append(session)
    day_list = sorted(day_map.items(), key=lambda item: item[0])
    users = User.query.order_by(User.email.asc()).all()
    return render_template(
        'admin/sessions/week_detail.html',
        week=week,
        day_list=day_list,
        users=users,
        categories=_session_categories()
    )


@admin_bp.route('/sessions/week/<int:week_id>/publish', methods=['POST'])
@login_required
@admin_required
def sessions_week_publish(week_id):
    week = SessionWeek.query.get_or_404(week_id)
    if week.status != 'published':
        week.status = 'published'
        week.published_at = datetime.utcnow()
        week.published_by = current_user.id
        db.session.commit()
        flash('Weekly timetable published.', 'success')
    return redirect(url_for('admin.sessions_week_view', week_id=week.id))


@admin_bp.route('/sessions/week/<int:week_id>/archive', methods=['POST'])
@login_required
@admin_required
def sessions_week_archive(week_id):
    week = SessionWeek.query.get_or_404(week_id)
    week.status = 'archived'
    db.session.commit()
    flash('Weekly timetable archived.', 'success')
    return redirect(url_for('admin.sessions_week_view', week_id=week.id))


@admin_bp.route('/sessions/session/add/<int:week_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def sessions_session_add(week_id):
    week = SessionWeek.query.get_or_404(week_id)
    users = User.query.order_by(User.email.asc()).all()
    if request.method == 'POST':
        session_date = request.form.get('session_date')
        start_time = request.form.get('start_time')
        topic = request.form.get('topic')
        category = request.form.get('category')
        mode = request.form.get('mode')
        meeting_link = request.form.get('meeting_link')
        location = request.form.get('location')
        teaching_minutes = request.form.get('teaching_minutes') or 60
        questions_minutes = request.form.get('questions_minutes') or 15
        instructor_user_id = request.form.get('instructor_user_id')
        status = request.form.get('status') or 'scheduled'

        if not session_date or not start_time or not topic or not category or not instructor_user_id:
            flash('Please fill all required fields.', 'error')
            return redirect(url_for('admin.sessions_session_add', week_id=week.id))

        try:
            session_date_val = datetime.strptime(session_date, '%Y-%m-%d').date()
            start_time_val = datetime.strptime(start_time, '%H:%M').time()
        except ValueError:
            flash('Invalid date/time format.', 'error')
            return redirect(url_for('admin.sessions_session_add', week_id=week.id))

        day_of_week = session_date_val.weekday()
        session = SessionSchedule(
            week_id=week.id,
            session_date=session_date_val,
            day_of_week=day_of_week,
            start_time=start_time_val,
            topic=topic,
            category=category,
            mode=mode,
            meeting_link=meeting_link,
            location=location,
            teaching_minutes=int(teaching_minutes),
            questions_minutes=int(questions_minutes),
            instructor_user_id=int(instructor_user_id),
            status=status,
            created_by=current_user.id,
        )
        db.session.add(session)
        db.session.commit()
        flash('Session added.', 'success')
        return redirect(url_for('admin.sessions_week_view', week_id=week.id))

    return render_template(
        'admin/sessions/session_form.html',
        week=week,
        session=None,
        users=users,
        categories=_session_categories()
    )


@admin_bp.route('/sessions/session/<int:session_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def sessions_session_edit(session_id):
    session = SessionSchedule.query.get_or_404(session_id)
    week = session.week
    users = User.query.order_by(User.email.asc()).all()
    if request.method == 'POST':
        session_date = request.form.get('session_date')
        start_time = request.form.get('start_time')
        topic = request.form.get('topic')
        category = request.form.get('category')
        mode = request.form.get('mode')
        meeting_link = request.form.get('meeting_link')
        location = request.form.get('location')
        teaching_minutes = request.form.get('teaching_minutes') or 60
        questions_minutes = request.form.get('questions_minutes') or 15
        instructor_user_id = request.form.get('instructor_user_id')
        status = request.form.get('status') or 'scheduled'

        if not session_date or not start_time or not topic or not category or not instructor_user_id:
            flash('Please fill all required fields.', 'error')
            return redirect(url_for('admin.sessions_session_edit', session_id=session.id))

        try:
            session_date_val = datetime.strptime(session_date, '%Y-%m-%d').date()
            start_time_val = datetime.strptime(start_time, '%H:%M').time()
        except ValueError:
            flash('Invalid date/time format.', 'error')
            return redirect(url_for('admin.sessions_session_edit', session_id=session.id))

        session.session_date = session_date_val
        session.day_of_week = session_date_val.weekday()
        session.start_time = start_time_val
        session.topic = topic
        session.category = category
        session.mode = mode
        session.meeting_link = meeting_link
        session.location = location
        session.teaching_minutes = int(teaching_minutes)
        session.questions_minutes = int(questions_minutes)
        session.instructor_user_id = int(instructor_user_id)
        session.status = status
        db.session.commit()
        flash('Session updated.', 'success')
        return redirect(url_for('admin.sessions_week_view', week_id=week.id))

    return render_template(
        'admin/sessions/session_form.html',
        week=week,
        session=session,
        users=users,
        categories=_session_categories()
    )


@admin_bp.route('/sessions/session/<int:session_id>/delete', methods=['POST'])
@login_required
@admin_required
def sessions_session_delete(session_id):
    session = SessionSchedule.query.get_or_404(session_id)
    week_id = session.week_id
    db.session.delete(session)
    db.session.commit()
    flash('Session removed.', 'success')
    return redirect(url_for('admin.sessions_week_view', week_id=week_id))


@admin_bp.route('/sessions/reports')
@login_required
@admin_required
def sessions_reports():
    reports = SessionReport.query.order_by(SessionReport.submitted_at.desc()).all()
    users = User.query.order_by(User.email.asc()).all()
    return render_template('admin/sessions/reports.html', reports=reports, users=users)


@admin_bp.route('/sessions/reports/<int:report_id>/approve', methods=['POST'])
@login_required
@admin_required
def sessions_report_approve(report_id):
    report = SessionReport.query.get_or_404(report_id)
    winner_user_id = request.form.get('winner_user_id')
    if not winner_user_id:
        flash('Select a winner to award points.', 'error')
        return redirect(url_for('admin.sessions_reports'))
    winner = User.query.get(int(winner_user_id))
    if not winner or not winner.member:
        flash('Selected user does not have a member profile.', 'error')
        return redirect(url_for('admin.sessions_reports'))

    if report.status != 'approved':
        report.status = 'approved'
        report.approved_by = current_user.id
        report.approved_at = datetime.utcnow()
        report.winner_user_id = winner.id
        report.points_awarded = 5

        transaction = RewardTransaction(
            member_id=winner.member.id,
            points=5,
            transaction_type='session_winner',
            reason=f"Session winner: {report.session.topic} on {report.session.session_date}",
            admin_id=current_user.id
        )
        db.session.add(transaction)
        db.session.commit()

    flash('Report approved and points awarded.', 'success')
    return redirect(url_for('admin.sessions_reports'))


@admin_bp.route('/sessions/reports/<int:report_id>/reject', methods=['POST'])
@login_required
@admin_required
def sessions_report_reject(report_id):
    report = SessionReport.query.get_or_404(report_id)
    report.status = 'rejected'
    report.approved_by = current_user.id
    report.approved_at = datetime.utcnow()
    db.session.commit()
    flash('Report rejected.', 'warning')
    return redirect(url_for('admin.sessions_reports'))


# Teams
def _default_team_names():
    return [
        'Alpha Company',
        'Bravo Company',
        'Charlie Company',
        'Delta Company',
        'Echo Company',
        'Foxtrot Company',
        'Golf Company',
        'Hotel Company',
        'India Company',
        'Juliet Company',
    ]


@admin_bp.route('/teams')
@login_required
@admin_required
def teams_index():
    teams = Team.query.order_by(Team.rating.desc(), Team.name.asc()).all()
    return render_template('admin/teams/index.html', teams=teams)


@admin_bp.route('/teams/seed', methods=['POST'])
@login_required
@admin_required
def teams_seed():
    existing = {t.name for t in Team.query.all()}
    created = 0
    for name in _default_team_names():
        if name not in existing:
            db.session.add(Team(name=name, rating=0))
            created += 1
    db.session.commit()
    flash(f'{created} teams created.', 'success')
    return redirect(url_for('admin.teams_index'))


@admin_bp.route('/teams/<int:team_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def teams_view(team_id):
    team = Team.query.get_or_404(team_id)
    members = Member.query.order_by(Member.full_name.asc()).all()
    if request.method == 'POST':
        team.description = request.form.get('description')
        rating = request.form.get('rating')
        try:
            team.rating = max(0, min(5, int(rating)))
        except (TypeError, ValueError):
            team.rating = 0
        db.session.commit()
        flash('Team updated.', 'success')
        return redirect(url_for('admin.teams_view', team_id=team.id))
    team_members = team.members.join(Member).order_by(Member.full_name.asc()).all()
    return render_template('admin/teams/detail.html', team=team, team_members=team_members, members=members)


@admin_bp.route('/teams/<int:team_id>/assign', methods=['POST'])
@login_required
@admin_required
def teams_assign_member(team_id):
    team = Team.query.get_or_404(team_id)
    member_id = request.form.get('member_id')
    is_leader = bool(request.form.get('is_leader'))
    if not member_id:
        flash('Select a member to assign.', 'error')
        return redirect(url_for('admin.teams_view', team_id=team.id))
    existing = TeamMember.query.filter_by(team_id=team.id, member_id=int(member_id)).first()
    if existing:
        flash('Member already in this team.', 'warning')
        return redirect(url_for('admin.teams_view', team_id=team.id))
    if is_leader:
        TeamMember.query.filter_by(team_id=team.id, is_leader=True).update({'is_leader': False})
    tm = TeamMember(team_id=team.id, member_id=int(member_id), is_leader=is_leader)
    db.session.add(tm)
    db.session.commit()
    flash('Member assigned to team.', 'success')
    return redirect(url_for('admin.teams_view', team_id=team.id))


@admin_bp.route('/teams/<int:team_id>/members/<int:team_member_id>/remove', methods=['POST'])
@login_required
@admin_required
def teams_remove_member(team_id, team_member_id):
    tm = TeamMember.query.get_or_404(team_member_id)
    if tm.team_id != team_id:
        flash('Invalid team member.', 'error')
        return redirect(url_for('admin.teams_view', team_id=team_id))
    db.session.delete(tm)
    db.session.commit()
    flash('Member removed from team.', 'success')
    return redirect(url_for('admin.teams_view', team_id=team_id))


@admin_bp.route('/teams/<int:team_id>/members/<int:team_member_id>/leader', methods=['POST'])
@login_required
@admin_required
def teams_set_leader(team_id, team_member_id):
    tm = TeamMember.query.get_or_404(team_member_id)
    if tm.team_id != team_id:
        flash('Invalid team member.', 'error')
        return redirect(url_for('admin.teams_view', team_id=team_id))
    TeamMember.query.filter_by(team_id=team_id, is_leader=True).update({'is_leader': False})
    tm.is_leader = True
    db.session.commit()
    flash('Team leader updated.', 'success')
    return redirect(url_for('admin.teams_view', team_id=team_id))
