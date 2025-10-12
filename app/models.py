from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='student')  # admin or student
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to member profile
    member = db.relationship('Member', backref='user', uselist=False, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(100))  # e.g., "Software Developer", "Data Scientist"
    bio = db.Column(db.Text)
    profile_image = db.Column(db.String(200))
    course = db.Column(db.String(100))  # e.g., "Computer Science", "IT"
    year = db.Column(db.String(20))  # e.g., "Year 2", "Graduate"
    status = db.Column(db.String(20), default='student')  # student or alumni
    phone = db.Column(db.String(20))
    github = db.Column(db.String(200))
    linkedin = db.Column(db.String(200))
    projects_json = db.Column(db.Text)  # JSON string of projects
    areas_of_interest = db.Column(db.Text)  # Comma-separated areas
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Digital ID fields
    member_id_number = db.Column(db.String(20), unique=True)  # Format: DC-YYYY-XXXX
    digital_id_path = db.Column(db.String(200))  # Path to generated ID image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to projects
    projects = db.relationship('Project', backref='member', lazy='dynamic')
    
    # Relationships for rewards and payments
    reward_transactions = db.relationship('RewardTransaction', backref='member', lazy='dynamic', foreign_keys='RewardTransaction.member_id')
    member_trophies = db.relationship('MemberTrophy', backref='member', lazy='dynamic')
    membership_payments = db.relationship('MembershipPayment', backref='member', lazy='dynamic')
    
    def get_projects(self):
        if self.projects_json:
            try:
                return json.loads(self.projects_json)
            except:
                return []
        return []
    
    def set_projects(self, projects_list):
        self.projects_json = json.dumps(projects_list)
    
    def get_areas_list(self):
        if self.areas_of_interest:
            return [area.strip() for area in self.areas_of_interest.split(',')]
        return []
    
    def generate_member_id(self):
        """Generate a unique member ID number in format DC-YYYY-XXXX"""
        if self.member_id_number:
            return self.member_id_number
        
        year = self.created_at.year if self.created_at else datetime.utcnow().year
        
        # Find the highest number for this year
        prefix = f'DC-{year}-'
        last_member = Member.query.filter(
            Member.member_id_number.like(f'{prefix}%')
        ).order_by(Member.member_id_number.desc()).first()
        
        if last_member and last_member.member_id_number:
            try:
                last_number = int(last_member.member_id_number.split('-')[-1])
                new_number = last_number + 1
            except:
                new_number = 1
        else:
            new_number = 1
        
        self.member_id_number = f'{prefix}{new_number:04d}'
        return self.member_id_number
    
    def needs_id_regeneration(self):
        """Check if digital ID needs to be regenerated"""
        # Regenerate if no ID exists or no image file
        if not self.digital_id_path:
            return True
        
        # Check if the file actually exists
        import os
        from flask import current_app
        if current_app:
            id_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'digital_ids', self.digital_id_path)
            if not os.path.exists(id_path):
                return True
        
        return False
    
    def get_total_points(self):
        """Calculate total reward points from all transactions"""
        total = db.session.query(db.func.sum(RewardTransaction.points)).filter(
            RewardTransaction.member_id == self.id
        ).scalar()
        return total or 0
    
    def get_current_trophies(self):
        """Get all earned trophies"""
        return [mt.trophy for mt in self.member_trophies.order_by(MemberTrophy.earned_at.desc()).all()]
    
    def has_valid_membership(self):
        """Check if any active payment covers today"""
        today = datetime.utcnow().date()
        valid_payment = MembershipPayment.query.filter(
            MembershipPayment.member_id == self.id,
            MembershipPayment.start_date <= today,
            MembershipPayment.end_date >= today
        ).first()
        return valid_payment is not None
    
    def get_membership_status(self):
        """Return membership status: 'valid', 'expired', or 'none'"""
        if not self.membership_payments.first():
            return 'none'
        
        if self.has_valid_membership():
            return 'valid'
        
        return 'expired'
    
    def get_latest_payment(self):
        """Get the most recent payment"""
        return self.membership_payments.order_by(MembershipPayment.end_date.desc()).first()
    
    def get_days_since_expiration(self):
        """Get number of days since membership expired (0 if valid or no payments)"""
        latest_payment = self.get_latest_payment()
        if not latest_payment:
            return 0
        
        if self.has_valid_membership():
            return 0
        
        today = datetime.utcnow().date()
        days_expired = (today - latest_payment.end_date).days
        return max(0, days_expired)
    
    def __repr__(self):
        return f'<Member {self.full_name}>'

class Leader(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    position = db.Column(db.String(100), nullable=False)  # e.g., "President", "Vice President"
    display_order = db.Column(db.Integer, default=0)
    
    # Relationship to User and Member
    user = db.relationship('User', backref='leader')
    
    @property
    def member(self):
        """Get the member profile for this leader"""
        return self.user.member if self.user else None
    
    def __repr__(self):
        return f'<Leader {self.position}>'

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))
    category = db.Column(db.String(50), default='general')  # hackathon, achievement, general
    published_date = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<News {self.title}>'

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    category = db.Column(db.String(50), default='workshop')  # hackathon, workshop, tech_talk, social_event
    image = db.Column(db.String(200))  # Event banner image
    max_attendees = db.Column(db.Integer)  # Optional capacity limit
    allows_check_in = db.Column(db.Boolean, default=True)  # Enable attendance tracking
    check_in_points = db.Column(db.Integer, default=0)  # Points awarded for attending
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_upcoming(self):
        """Check if event is in the future"""
        return self.event_date > datetime.utcnow()
    
    def is_ongoing(self):
        """Check if event is currently happening (within 24 hours of start time)"""
        now = datetime.utcnow()
        time_diff = (self.event_date - now).total_seconds() / 3600  # Hours
        return -24 <= time_diff <= 0
    
    def get_rsvp_stats(self):
        """Get RSVP statistics"""
        total = len(self.rsvps)
        pending = sum(1 for r in self.rsvps if r.status == 'pending')
        approved = sum(1 for r in self.rsvps if r.status == 'approved')
        rejected = sum(1 for r in self.rsvps if r.status == 'rejected')
        return {
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected
        }
    
    def __repr__(self):
        return f'<Event {self.title}>'

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(200))
    github_link = db.Column(db.String(200))
    demo_link = db.Column(db.String(200))
    technologies = db.Column(db.String(200))  # Comma-separated tech stack
    team_members = db.Column(db.String(200))  # Comma-separated member names
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # New fields for member projects
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=True)  # NULL for admin projects
    is_public = db.Column(db.Boolean, default=True)  # Public/private setting
    is_featured = db.Column(db.Boolean, default=False)  # Admin can feature on homepage
    is_admin_project = db.Column(db.Boolean, default=False)  # Distinguish admin vs member projects
    
    def get_technologies_list(self):
        if self.technologies:
            return [tech.strip() for tech in self.technologies.split(',')]
        return []
    
    def get_team_list(self):
        if self.team_members:
            return [member.strip() for member in self.team_members.split(',')]
        return []
    
    def __repr__(self):
        return f'<Project {self.title}>'

class Gallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # image or video
    url = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Gallery {self.type}>'

class Technology(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(50), nullable=False)  # web, mobile, ai, iot, data, other
    description = db.Column(db.Text)
    icon = db.Column(db.String(100))  # Font Awesome icon class
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Technology {self.name}>'

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(100))  # Font Awesome icon class
    
    def __repr__(self):
        return f'<Topic {self.name}>'

class Newsletter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<Newsletter {self.email or self.phone}>'

class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(250), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.Text)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), default='general')
    featured_image = db.Column(db.String(200))
    tags = db.Column(db.String(200))  # Comma-separated tags
    is_published = db.Column(db.Boolean, default=False)
    published_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    
    # Relationship
    author = db.relationship('User', backref='blog_posts')
    
    def get_tags_list(self):
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []
    
    def set_tags_list(self, tags_list):
        self.tags = ', '.join(tags_list)
    
    def __repr__(self):
        return f'<Blog {self.title}>'

class RSVP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    acceptance_code = db.Column(db.String(10), unique=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    course = db.Column(db.String(100))
    year = db.Column(db.String(20))
    dietary_requirements = db.Column(db.Text)
    emergency_contact = db.Column(db.String(100))
    emergency_phone = db.Column(db.String(20))
    additional_notes = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Check-in fields
    checked_in = db.Column(db.Boolean, default=False)
    checked_in_at = db.Column(db.DateTime)
    checked_in_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    event = db.relationship('Event', backref='rsvps')
    member = db.relationship('Member', backref='rsvps')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_rsvps')
    checker = db.relationship('User', foreign_keys=[checked_in_by], backref='checked_in_rsvps')
    
    def generate_acceptance_code(self):
        """Generate a unique acceptance code"""
        import random
        import string
        
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not RSVP.query.filter_by(acceptance_code=code).first():
                self.acceptance_code = code
                break
    
    def __repr__(self):
        return f'<RSVP {self.full_name} - {self.event.title if self.event else "Unknown Event"}>'


class RewardTransaction(db.Model):
    """Track reward points awarded or deducted from members"""
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False)  # Positive for awards, negative for deductions
    transaction_type = db.Column(db.String(50), nullable=False)  # 'manual', 'event_checkin', 'achievement', etc.
    reason = db.Column(db.Text, nullable=False)  # Description of why points were awarded/deducted
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)  # If related to an event
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Admin who made the transaction
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    admin = db.relationship('User', backref='reward_transactions')
    event = db.relationship('Event', backref='reward_transactions')
    
    def __repr__(self):
        return f'<RewardTransaction {self.member_id}: {self.points} points>'


class Trophy(db.Model):
    """Define achievement levels and trophies"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    points_required = db.Column(db.Integer, nullable=False)
    icon = db.Column(db.String(100))  # Font Awesome icon class or emoji
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    member_trophies = db.relationship('MemberTrophy', backref='trophy', lazy='dynamic')
    
    def __repr__(self):
        return f'<Trophy {self.name}: {self.points_required} points>'


class MemberTrophy(db.Model):
    """Track which members have earned which trophies"""
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    trophy_id = db.Column(db.Integer, db.ForeignKey('trophy.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint: member can only earn each trophy once
    __table_args__ = (db.UniqueConstraint('member_id', 'trophy_id', name='_member_trophy_uc'),)
    
    def __repr__(self):
        return f'<MemberTrophy {self.member_id} - {self.trophy_id}>'


class MembershipPayment(db.Model):
    """Track membership fee payments"""
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)  # When payment was made
    start_date = db.Column(db.Date, nullable=False)  # Membership period start
    end_date = db.Column(db.Date, nullable=False)  # Membership period end
    payment_method = db.Column(db.String(50))  # cash, bank_transfer, mobile_money, etc.
    notes = db.Column(db.Text)  # Additional notes about the payment
    recorded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Admin who recorded payment
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    recorder = db.relationship('User', backref='recorded_payments')
    
    def is_active(self):
        """Check if payment period is currently active"""
        today = datetime.utcnow().date()
        return self.start_date <= today <= self.end_date
    
    def is_expired(self):
        """Check if payment period has expired"""
        today = datetime.utcnow().date()
        return today > self.end_date
    
    def days_remaining(self):
        """Get number of days remaining (negative if expired)"""
        today = datetime.utcnow().date()
        return (self.end_date - today).days
    
    def __repr__(self):
        return f'<MembershipPayment {self.member_id}: ${self.amount} ({self.start_date} to {self.end_date})>'


class SystemSettings(db.Model):
    """Store system-wide settings"""
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)  # What this setting controls
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    updater = db.relationship('User', backref='system_settings_updates')
    
    @staticmethod
    def get_setting(key, default=None):
        """Get a setting value by key"""
        setting = SystemSettings.query.filter_by(setting_key=key).first()
        return setting.setting_value if setting else default
    
    @staticmethod
    def set_setting(key, value, description=None, user_id=None):
        """Set or update a setting value"""
        setting = SystemSettings.query.filter_by(setting_key=key).first()
        if setting:
            setting.setting_value = value
            setting.updated_by = user_id
            if description:
                setting.description = description
        else:
            setting = SystemSettings(
                setting_key=key,
                setting_value=value,
                description=description,
                updated_by=user_id
            )
            db.session.add(setting)
        return setting
    
    def __repr__(self):
        return f'<SystemSettings {self.setting_key}: {self.setting_value}>'