"""
Digital ID Card Generator
Generates professional digital ID cards with QR codes for members
"""

import os
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from flask import current_app, request
import requests


def generate_digital_id(member, base_url=None):
    """
    Generate a digital ID card for a member
    
    Args:
        member: Member object
        base_url: Base URL for QR code (optional, will use request context if available)
    
    Returns:
        str: Filename of the generated ID card
    """
    
    # Ensure member has an ID number
    if not member.member_id_number:
        member.generate_member_id()
    
    # Card dimensions
    CARD_WIDTH = 800
    CARD_HEIGHT = 500
    PADDING = 30
    
    # Colors (Digital Club theme)
    BG_COLOR = (15, 23, 42)  # Dark blue background
    ACCENT_COLOR = (0, 255, 255)  # Cyan accent
    TEXT_PRIMARY = (255, 255, 255)  # White
    TEXT_SECONDARY = (148, 163, 184)  # Gray
    CARD_BORDER = (0, 200, 200)  # Cyan border
    
    # Create the base image
    img = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Draw border
    border_width = 3
    draw.rectangle(
        [border_width, border_width, CARD_WIDTH - border_width, CARD_HEIGHT - border_width],
        outline=CARD_BORDER,
        width=border_width
    )
    
    # Draw accent line at top
    draw.rectangle([0, 0, CARD_WIDTH, 8], fill=ACCENT_COLOR)
    
    # Try to load custom fonts (fallback to default if not available)
    try:
        font_title = ImageFont.truetype("arial.ttf", 32)
        font_large = ImageFont.truetype("arial.ttf", 24)
        font_medium = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 14)
        font_tiny = ImageFont.truetype("arial.ttf", 12)
    except:
        # Fallback to default font
        font_title = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()
    
    # Add club logo (if exists)
    try:
        logo_path = os.path.join(current_app.root_path, 'static', 'DigitalClub_LOGO copy.svg')
        # For SVG, we'll just add text instead
        draw.text((PADDING, 20), "DIGITAL CLUB", fill=ACCENT_COLOR, font=font_large)
    except:
        draw.text((PADDING, 20), "DIGITAL CLUB", fill=ACCENT_COLOR, font=font_large)
    
    # Add subtitle
    draw.text((PADDING, 55), "KIUT", fill=TEXT_SECONDARY, font=font_small)
    
    # Add member photo (circular)
    photo_size = 180
    photo_x = PADDING + 20
    photo_y = 100
    
    try:
        if member.profile_image:
            profile_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], 
                'profiles', 
                member.profile_image
            )
            
            if os.path.exists(profile_path):
                profile_img = Image.open(profile_path)
                profile_img = profile_img.convert('RGB')
                profile_img = profile_img.resize((photo_size, photo_size), Image.Resampling.LANCZOS)
                
                # Create circular mask
                mask = Image.new('L', (photo_size, photo_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse([0, 0, photo_size, photo_size], fill=255)
                
                # Create circular image
                circular_img = Image.new('RGB', (photo_size, photo_size), BG_COLOR)
                circular_img.paste(profile_img, (0, 0), mask)
                
                # Draw circle border
                border_img = Image.new('RGBA', (photo_size + 8, photo_size + 8), (0, 0, 0, 0))
                border_draw = ImageDraw.Draw(border_img)
                border_draw.ellipse([0, 0, photo_size + 7, photo_size + 7], outline=ACCENT_COLOR, width=4)
                
                img.paste(circular_img, (photo_x, photo_y))
                img.paste(border_img, (photo_x - 4, photo_y - 4), border_img)
            else:
                # Draw placeholder circle
                draw.ellipse([photo_x, photo_y, photo_x + photo_size, photo_y + photo_size], 
                           outline=ACCENT_COLOR, width=3)
                # Add icon
                draw.text((photo_x + photo_size//2 - 20, photo_y + photo_size//2 - 20), 
                         "👤", font=font_title)
        else:
            # Draw placeholder circle
            draw.ellipse([photo_x, photo_y, photo_x + photo_size, photo_y + photo_size], 
                       outline=ACCENT_COLOR, width=3)
            draw.text((photo_x + photo_size//2 - 20, photo_y + photo_size//2 - 20), 
                     "👤", font=font_title)
    except Exception as e:
        # Draw placeholder on error
        draw.ellipse([photo_x, photo_y, photo_x + photo_size, photo_y + photo_size], 
                   outline=ACCENT_COLOR, width=3)
        draw.text((photo_x + photo_size//2 - 20, photo_y + photo_size//2 - 20), 
                 "👤", font=font_title)
    
    # Add member information (right side)
    info_x = photo_x + photo_size + 40
    info_y = 100
    line_height = 35
    
    # Member name (bold, larger)
    draw.text((info_x, info_y), member.full_name.upper(), fill=TEXT_PRIMARY, font=font_title)
    info_y += 45
    
    # Member ID
    draw.text((info_x, info_y), "ID:", fill=TEXT_SECONDARY, font=font_small)
    draw.text((info_x + 50, info_y), member.member_id_number, fill=ACCENT_COLOR, font=font_large)
    info_y += line_height
    
    # Course
    if member.course:
        draw.text((info_x, info_y), "Course:", fill=TEXT_SECONDARY, font=font_small)
        draw.text((info_x + 90, info_y), member.course, fill=TEXT_PRIMARY, font=font_medium)
        info_y += line_height
    
    # Year
    if member.year:
        draw.text((info_x, info_y), "Year:", fill=TEXT_SECONDARY, font=font_small)
        draw.text((info_x + 90, info_y), member.year, fill=TEXT_PRIMARY, font=font_medium)
        info_y += line_height
    
    # Status badge
    status_text = member.status.upper()
    status_color = (0, 255, 0) if member.status == 'student' else (255, 255, 0)
    
    # Draw status badge background
    badge_width = 120
    badge_height = 30
    badge_x = info_x
    badge_y = info_y
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
        radius=15,
        fill=(*status_color, 50),
        outline=status_color,
        width=2
    )
    draw.text((badge_x + 25, badge_y + 7), status_text, fill=status_color, font=font_small)
    info_y += 45
    
    # Join date
    if member.created_at:
        join_date = member.created_at.strftime('%B %Y')
        draw.text((info_x, info_y), f"Member Since: {join_date}", 
                 fill=TEXT_SECONDARY, font=font_tiny)
    
    # Generate QR code
    if not base_url:
        # Try to get base URL from request context
        try:
            base_url = request.url_root.rstrip('/')
        except:
            base_url = "https://digitalclub.kiut.ac.tz"
    
    qr_url = f"{base_url}/verify-id/{member.member_id_number}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color=ACCENT_COLOR, back_color=BG_COLOR)
    qr_img = qr_img.resize((140, 140), Image.Resampling.LANCZOS)
    
    # Position QR code at bottom right
    qr_x = CARD_WIDTH - 140 - PADDING
    qr_y = CARD_HEIGHT - 140 - PADDING
    img.paste(qr_img, (qr_x, qr_y))
    
    # Add QR code label
    draw.text((qr_x + 20, qr_y + 145), "SCAN TO VERIFY", 
             fill=TEXT_SECONDARY, font=font_tiny)
    
    # Add footer text
    footer_text = "This card verifies membership in KIUT Digital Club"
    draw.text((PADDING, CARD_HEIGHT - 25), footer_text, 
             fill=TEXT_SECONDARY, font=font_tiny)
    
    # Save the image
    filename = f"{member.member_id_number}.png"
    output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'digital_ids')
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, filename)
    img.save(output_path, 'PNG', quality=95)
    
    # Update member record
    member.digital_id_path = filename
    
    return filename


def delete_digital_id(member):
    """Delete a member's digital ID file"""
    if not member.digital_id_path:
        return
    
    try:
        id_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'], 
            'digital_ids', 
            member.digital_id_path
        )
        if os.path.exists(id_path):
            os.remove(id_path)
    except Exception as e:
        print(f"Error deleting digital ID: {e}")

