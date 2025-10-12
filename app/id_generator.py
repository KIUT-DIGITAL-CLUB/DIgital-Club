"""
Digital ID Card Generator
Generates professional digital ID cards with QR codes for members
Modern design with front and back views, standard ID dimensions
"""

import os
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from flask import current_app, request
import requests


def load_fonts():
    """Load fonts with proper fallbacks"""
    try:
        return {
            'title': ImageFont.truetype("arial.ttf", 42),
            'large': ImageFont.truetype("arial.ttf", 28),
            'medium': ImageFont.truetype("arial.ttf", 20),
            'small': ImageFont.truetype("arial.ttf", 16),
            'tiny': ImageFont.truetype("arial.ttf", 12),
            'micro': ImageFont.truetype("arial.ttf", 10)
        }
    except:
        return {
            'title': ImageFont.load_default(),
            'large': ImageFont.load_default(),
            'medium': ImageFont.load_default(),
            'small': ImageFont.load_default(),
            'tiny': ImageFont.load_default(),
            'micro': ImageFont.load_default()
        }


def draw_gradient_background(draw, width, height, color1, color2, vertical=False):
    """Draw a smooth gradient background"""
    if vertical:
        for y in range(height):
            ratio = y / height
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.rectangle([0, y, width, y + 1], fill=(r, g, b))
    else:
        for x in range(width):
            ratio = x / width
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.rectangle([x, 0, x + 1, height], fill=(r, g, b))


def add_geometric_patterns(draw, width, height):
    """Add subtle geometric background patterns"""
    pattern_color = (255, 255, 255, 15)  # Very transparent white
    
    # Draw diagonal lines
    for i in range(0, width + height, 60):
        draw.line([(i, 0), (i - height, height)], fill=pattern_color, width=1)
    
    # Draw dots pattern
    for x in range(30, width, 40):
        for y in range(30, height, 40):
            draw.ellipse([x-1, y-1, x+1, y+1], fill=pattern_color)


def load_and_process_logo(logo_path, target_size):
    """Load SVG logo and convert to usable image"""
    try:
        # Try to use cairosvg if available for best quality
        try:
            import cairosvg
            png_data = cairosvg.svg2png(url=logo_path, output_width=target_size[0], output_height=target_size[1])
            logo = Image.open(BytesIO(png_data))
            return logo.convert('RGBA')
        except ImportError:
            pass
        except Exception as e:
            print(f"cairosvg error: {e}")
        
        # Try svglib + reportlab as alternative
        try:
            from svglib.svglib import svg2rlg
            from reportlab.graphics import renderPM
            drawing = svg2rlg(logo_path)
            if drawing:
                # Scale drawing to target size
                scale_x = target_size[0] / drawing.width
                scale_y = target_size[1] / drawing.height
                scale = min(scale_x, scale_y)
                drawing.width = target_size[0]
                drawing.height = target_size[1]
                drawing.scale(scale, scale)
                
                png_data = renderPM.drawToString(drawing, fmt='PNG')
                logo = Image.open(BytesIO(png_data))
                return logo.convert('RGBA')
        except ImportError:
            pass
        except Exception as e:
            print(f"svglib error: {e}")
        
        # Fallback: try to open as PNG if it exists
        png_path = logo_path.replace('.svg', '.png')
        if os.path.exists(png_path):
            logo = Image.open(png_path)
            logo = logo.resize(target_size, Image.Resampling.LANCZOS)
            return logo.convert('RGBA')
        
        # Last resort: try opening the SVG as an image (some PIL versions support it)
        logo = Image.open(logo_path)
        logo = logo.resize(target_size, Image.Resampling.LANCZOS)
        return logo.convert('RGBA')
    except Exception as e:
        print(f"Logo loading error: {e}")
        return None


def generate_digital_id_front(member, base_url=None):
    """
    Generate the FRONT side of the digital ID card
    
    Args:
        member: Member object
        base_url: Base URL for QR code (optional)
    
    Returns:
        Image: PIL Image object of the front card
    """
    # Standard ID card dimensions (1016x640 for high quality)
    CARD_WIDTH = 1016
    CARD_HEIGHT = 640
    
    # Color scheme from Digital Club logo
    COLOR_BLUE = (33, 121, 184)  # #2179b8
    COLOR_GREEN = (66, 177, 102)  # #42b166
    COLOR_LIGHT = (52, 181, 89)  # #34b559
    COLOR_DARK_BLUE = (36, 125, 185)  # #247db9
    BG_DARK = (15, 25, 45)
    TEXT_WHITE = (255, 255, 255)
    TEXT_LIGHT = (200, 210, 230)
    TEXT_GOLD = (255, 215, 0)
    
    # Create base image with gradient
    img = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Draw gradient background (blue to dark)
    draw_gradient_background(draw, CARD_WIDTH, CARD_HEIGHT, COLOR_BLUE, BG_DARK, vertical=True)
    
    # Add geometric patterns
    add_geometric_patterns(draw, CARD_WIDTH, CARD_HEIGHT)
    
    # Load fonts
    fonts = load_fonts()
    
    # Add decorative top bar with gradient effect
    for i in range(25):
        alpha = int(255 * (1 - i/25))
        color = (*COLOR_GREEN, alpha)
        draw.rectangle([0, i, CARD_WIDTH, i+1], fill=color)
    
    # Load and add logo
    logo_path = os.path.join(current_app.root_path, 'static', 'DigitalClub_LOGO copy.svg')
    logo = load_and_process_logo(logo_path, (180, 180))
    
    if logo:
        # Position logo at top left
        img.paste(logo, (40, 40), logo)
    else:
        # Fallback text logo
        draw.text((40, 50), "DIGITAL CLUB", fill=COLOR_GREEN, font=fonts['title'])
        draw.text((40, 95), "KIUT", fill=TEXT_LIGHT, font=fonts['medium'])
    
    # Add decorative corner elements
    corner_size = 40
    corner_color = (*COLOR_GREEN, 100)
    # Top right corner
    draw.polygon([(CARD_WIDTH, 0), (CARD_WIDTH - corner_size, 0), (CARD_WIDTH, corner_size)], fill=corner_color)
    # Bottom left corner
    draw.polygon([(0, CARD_HEIGHT), (corner_size, CARD_HEIGHT), (0, CARD_HEIGHT - corner_size)], fill=corner_color)
    
    # Add member photo (rounded square with border)
    photo_size = 200
    photo_x = 60
    photo_y = 250
    
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
                
                # Create rounded rectangle mask
                mask = Image.new('L', (photo_size, photo_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, photo_size, photo_size], radius=20, fill=255)
                
                # Create rounded image
                rounded_img = Image.new('RGB', (photo_size, photo_size), BG_DARK)
                rounded_img.paste(profile_img, (0, 0), mask)
                
                # Draw border
                img.paste(rounded_img, (photo_x, photo_y))
                draw.rounded_rectangle(
                    [photo_x-3, photo_y-3, photo_x+photo_size+3, photo_y+photo_size+3],
                    radius=20,
                    outline=COLOR_GREEN,
                    width=4
                )
            else:
                # Draw placeholder
                draw.rounded_rectangle(
                    [photo_x, photo_y, photo_x+photo_size, photo_y+photo_size],
                    radius=20,
                    outline=COLOR_GREEN,
                    width=3
                )
                draw.text((photo_x + 70, photo_y + 80), "📷", font=fonts['title'])
        else:
            # Draw placeholder
            draw.rounded_rectangle(
                [photo_x, photo_y, photo_x+photo_size, photo_y+photo_size],
                radius=20,
                outline=COLOR_GREEN,
                width=3
            )
            draw.text((photo_x + 70, photo_y + 80), "📷", font=fonts['title'])
    except Exception as e:
        # Draw placeholder on error
        draw.rounded_rectangle(
            [photo_x, photo_y, photo_x+photo_size, photo_y+photo_size],
            radius=20,
            outline=COLOR_GREEN,
            width=3
        )
    
    # Add member information (right side)
    info_x = 320
    info_y = 180
    
    # Draw info background panel with transparency
    panel_color = (*BG_DARK, 180)
    draw.rounded_rectangle(
        [info_x - 20, info_y - 20, CARD_WIDTH - 40, 550],
        radius=15,
        fill=panel_color
    )
    
    # Member name
    name_lines = []
    name = member.full_name.upper()
    if len(name) > 20:
        words = name.split()
        line1 = []
        line2 = []
        for word in words:
            if len(' '.join(line1 + [word])) <= 20:
                line1.append(word)
            else:
                line2.append(word)
        name_lines.append(' '.join(line1))
        if line2:
            name_lines.append(' '.join(line2))
    else:
        name_lines.append(name)
    
    for i, line in enumerate(name_lines):
        draw.text((info_x, info_y + i * 45), line, fill=TEXT_WHITE, font=fonts['large'])
    
    info_y += len(name_lines) * 45 + 30
    
    # Separator line
    draw.line([(info_x, info_y), (CARD_WIDTH - 60, info_y)], fill=COLOR_GREEN, width=2)
    info_y += 25
    
    # Member ID with highlight
    draw.text((info_x, info_y), "MEMBER ID", fill=TEXT_LIGHT, font=fonts['tiny'])
    info_y += 25
    draw.text((info_x, info_y), member.member_id_number, fill=TEXT_GOLD, font=fonts['large'])
    info_y += 50
    
    # Course and Year
    if member.course:
        draw.text((info_x, info_y), "COURSE", fill=TEXT_LIGHT, font=fonts['tiny'])
        info_y += 20
        course_text = member.course[:30]  # Limit length
        draw.text((info_x, info_y), course_text, fill=TEXT_WHITE, font=fonts['small'])
        info_y += 35
    
    if member.year:
        draw.text((info_x, info_y), "YEAR", fill=TEXT_LIGHT, font=fonts['tiny'])
        info_y += 20
        draw.text((info_x, info_y), member.year, fill=TEXT_WHITE, font=fonts['small'])
        info_y += 35
    
    # Status badge
    status_text = member.status.upper()
    status_color = COLOR_GREEN if member.status == 'student' else TEXT_GOLD
    
    badge_width = 140
    badge_height = 35
    badge_x = info_x
    badge_y = info_y + 10
    
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
        radius=17,
        fill=(*status_color, 40),
        outline=status_color,
        width=3
    )
    # Center text in badge
    draw.text((badge_x + 30, badge_y + 8), status_text, fill=status_color, font=fonts['medium'])
    
    # Generate QR code (bottom right)
    if not base_url:
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
    
    qr_img = qr.make_image(fill_color=TEXT_WHITE, back_color=BG_DARK)
    qr_img = qr_img.resize((140, 140), Image.Resampling.LANCZOS)
    
    # QR code with decorative border - positioned at bottom right
    qr_x = CARD_WIDTH - 180
    qr_y = CARD_HEIGHT - 180
    
    # Draw QR background
    draw.rounded_rectangle(
        [qr_x - 10, qr_y - 10, qr_x + 150, qr_y + 150],
        radius=10,
        fill=TEXT_WHITE
    )
    img.paste(qr_img, (qr_x, qr_y))
    
    # QR label
    draw.text((qr_x + 15, qr_y + 150), "SCAN TO VERIFY", fill=TEXT_LIGHT, font=fonts['micro'])
    
    # Validity date (bottom left)
    if member.created_at:
        valid_from = member.created_at.strftime('%m/%Y')
        draw.text((60, CARD_HEIGHT - 80), "VALID FROM", fill=TEXT_LIGHT, font=fonts['micro'])
        draw.text((60, CARD_HEIGHT - 60), valid_from, fill=TEXT_WHITE, font=fonts['small'])
    
    # Holographic accent line at bottom
    for i in range(10):
        alpha = int(100 * (1 - i/10))
        color = (*COLOR_LIGHT, alpha)
        draw.rectangle([0, CARD_HEIGHT - 10 + i, CARD_WIDTH, CARD_HEIGHT - 9 + i], fill=color)
    
    return img


def generate_digital_id_back(member, base_url=None):
    """
    Generate the BACK side of the digital ID card
    
    Args:
        member: Member object
        base_url: Base URL for QR code (optional)
    
    Returns:
        Image: PIL Image object of the back card
    """
    # Standard ID card dimensions
    CARD_WIDTH = 1016
    CARD_HEIGHT = 640
    
    # Color scheme
    COLOR_BLUE = (33, 121, 184)
    COLOR_GREEN = (66, 177, 102)
    BG_DARK = (15, 25, 45)
    TEXT_WHITE = (255, 255, 255)
    TEXT_LIGHT = (200, 210, 230)
    
    # Create base image
    img = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Draw gradient background
    draw_gradient_background(draw, CARD_WIDTH, CARD_HEIGHT, BG_DARK, COLOR_BLUE, vertical=True)
    
    # Add geometric patterns
    add_geometric_patterns(draw, CARD_WIDTH, CARD_HEIGHT)
    
    # Load fonts
    fonts = load_fonts()
    
    # Decorative top bar
    for i in range(25):
        alpha = int(255 * (1 - i/25))
        color = (*COLOR_GREEN, alpha)
        draw.rectangle([0, i, CARD_WIDTH, i+1], fill=color)
    
    # Load and add logo at top center
    logo_path = os.path.join(current_app.root_path, 'static', 'DigitalClub_LOGO copy.svg')
    logo = load_and_process_logo(logo_path, (140, 140))
    
    if logo:
        # Position logo at top center
        logo_x = CARD_WIDTH // 2 - 70
        img.paste(logo, (logo_x, 15), logo)
    
    # Title section (below logo)
    title_y = 60
    # draw.text((CARD_WIDTH // 2 - 180, title_y), "KIUT DIGITAL CLUB", fill=COLOR_GREEN, font=fonts['title'])
    # draw.text((CARD_WIDTH // 2 - 140, title_y + 50), "Karatina University Digital Club", fill=TEXT_LIGHT, font=fonts['small'])
    
    # Separator
    draw.line([(80, 140), (CARD_WIDTH - 80, 140)], fill=COLOR_GREEN, width=2)
    
    # Club information section
    info_y = 170
    padding_x = 80
    
    # About section
    draw.text((padding_x, info_y), "ABOUT THE CLUB", fill=COLOR_GREEN, font=fonts['medium'])
    info_y += 35
    
    about_text = [
        "The Digital Club is a community of tech enthusiasts,",
        "developers, and innovators at KIUT. We foster learning,",
        "collaboration, and innovation in technology."
    ]
    
    for line in about_text:
        draw.text((padding_x, info_y), line, fill=TEXT_LIGHT, font=fonts['small'])
        info_y += 25
    
    info_y += 20
    
    # Contact information
    draw.text((padding_x, info_y), "CONTACT INFORMATION", fill=COLOR_GREEN, font=fonts['medium'])
    info_y += 35
    
    contact_info = [
        "📧 Email: info@digitalclub.kiut.ac.tz",
        "🌐 Website: www.digitalclub.kiut.ac.tz",
        "📱 Phone: +254 XXX XXX XXX"
    ]
    
    for line in contact_info:
        draw.text((padding_x, info_y), line, fill=TEXT_LIGHT, font=fonts['small'])
        info_y += 25
    
    # Terms and conditions section (right side)
    terms_x = CARD_WIDTH // 2 + 40
    terms_y = 170
    
    draw.text((terms_x, terms_y), "TERMS & CONDITIONS", fill=COLOR_GREEN, font=fonts['medium'])
    terms_y += 35
    
    terms = [
        "• This card is non-transferable",
        "• Valid for current members only",
        "• Must be presented at club events",
        "• Report if lost or stolen",
        "• Subject to club regulations"
    ]
    
    for term in terms:
        draw.text((terms_x, terms_y), term, fill=TEXT_LIGHT, font=fonts['tiny'])
        terms_y += 22
    
    # QR code for club website (positioned at right side to avoid magnetic strip)
    if not base_url:
        try:
            base_url = request.url_root.rstrip('/')
        except:
            base_url = "https://digitalclub.kiut.ac.tz"
    
    club_qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    club_qr.add_data(base_url)
    club_qr.make(fit=True)
    
    qr_img = club_qr.make_image(fill_color=TEXT_WHITE, back_color=BG_DARK)
    qr_img = qr_img.resize((110, 110), Image.Resampling.LANCZOS)
    
    # Position QR at right side, above magnetic strip
    qr_x = CARD_WIDTH - 200
    qr_y = CARD_HEIGHT - 220
    
    # QR background
    draw.rounded_rectangle(
        [qr_x - 8, qr_y - 8, qr_x + 118, qr_y + 118],
        radius=8,
        fill=TEXT_WHITE
    )
    img.paste(qr_img, (qr_x, qr_y))
    
    # QR label
    draw.text((qr_x, qr_y + 120), "Visit Our Website", fill=TEXT_LIGHT, font=fonts['micro'])
    
    # Signature line (positioned above magnetic strip)
    draw.text((80, CARD_HEIGHT - 140), "Authorized Signature: ____________", fill=TEXT_LIGHT, font=fonts['tiny'])
    
    # Security features - magnetic strip effect (at bottom, not overlapping QR)
    strip_y = CARD_HEIGHT - 80
    for i in range(40):
        alpha = 200 - i * 2
        color = (50, 50, 50, alpha)
        draw.rectangle([0, strip_y + i, CARD_WIDTH, strip_y + i + 1], fill=color)
    
    # Footer (above magnetic strip)
    draw.text((CARD_WIDTH // 2 - 100, CARD_HEIGHT - 100), "© 2024 KIUT Digital Club", fill=TEXT_LIGHT, font=fonts['micro'])
    
    # Decorative corners
    corner_size = 40
    corner_color = (*COLOR_BLUE, 80)
    draw.polygon([(CARD_WIDTH, 0), (CARD_WIDTH - corner_size, 0), (CARD_WIDTH, corner_size)], fill=corner_color)
    draw.polygon([(0, CARD_HEIGHT), (corner_size, CARD_HEIGHT), (0, CARD_HEIGHT - corner_size)], fill=corner_color)
    
    return img


def generate_digital_id(member, base_url=None):
    """
    Generate both front and back digital ID cards for a member
    
    Args:
        member: Member object
        base_url: Base URL for QR code (optional, will use request context if available)
    
    Returns:
        tuple: (front_filename, back_filename)
    """
    
    # Ensure member has an ID number
    if not member.member_id_number:
        member.generate_member_id()
    
    # Generate front card
    front_img = generate_digital_id_front(member, base_url)
    
    # Generate back card
    back_img = generate_digital_id_back(member, base_url)
    
    # Save both images
    front_filename = f"{member.member_id_number}_front.png"
    back_filename = f"{member.member_id_number}_back.png"
    
    output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'digital_ids')
    os.makedirs(output_dir, exist_ok=True)
    
    front_path = os.path.join(output_dir, front_filename)
    back_path = os.path.join(output_dir, back_filename)
    
    front_img.save(front_path, 'PNG', quality=95)
    back_img.save(back_path, 'PNG', quality=95)
    
    # Update member record (store front path for backward compatibility)
    member.digital_id_path = front_filename
    
    return front_filename, back_filename


def delete_digital_id(member):
    """Delete a member's digital ID files (both front and back)"""
    if not member.digital_id_path:
        return
    
    try:
        # Delete front card
        front_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'], 
            'digital_ids', 
            member.digital_id_path
        )
        if os.path.exists(front_path):
            os.remove(front_path)
        
        # Delete back card
        back_filename = member.digital_id_path.replace('_front.png', '_back.png')
        if not back_filename.endswith('_back.png'):
            # Handle old format (no _front suffix)
            back_filename = member.digital_id_path.replace('.png', '_back.png')
        
        back_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'], 
            'digital_ids', 
            back_filename
        )
        if os.path.exists(back_path):
            os.remove(back_path)
    except Exception as e:
        print(f"Error deleting digital ID: {e}")

