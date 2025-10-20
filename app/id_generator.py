"""
Digital ID Card Generator - Premium Edition
Generates stunning, premium-quality digital ID cards with advanced visual effects
Features: Glass morphism, holographic accents, depth effects, modern design
Improved with a more appealing color scheme, better contrast, simplified effects for elegance,
improved layout balance, and adherence to design principles like hierarchy, alignment, and minimalism.
"""

import os
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from flask import current_app, request
import requests
import math


def load_fonts():
    """Load fonts with proper fallbacks - includes bold variants"""
    fonts = {}
    
    # Try to load preferred fonts in order of preference
    font_configs = [
        # Arial fonts (Windows)
        {'title': ("arialbd.ttf", 48), 'large': ("arialbd.ttf", 32), 'medium': ("arial.ttf", 22), 
         'small': ("arial.ttf", 18), 'tiny': ("arial.ttf", 14), 'micro': ("arial.ttf", 11)},
        # Liberation fonts (Linux)
        {'title': ("LiberationSans-Bold.ttf", 48), 'large': ("LiberationSans-Bold.ttf", 32), 
         'medium': ("LiberationSans-Regular.ttf", 22), 'small': ("LiberationSans-Regular.ttf", 18), 
         'tiny': ("LiberationSans-Regular.ttf", 14), 'micro': ("LiberationSans-Regular.ttf", 11)},
        # DejaVu fonts (Linux fallback)
        {'title': ("DejaVuSans-Bold.ttf", 48), 'large': ("DejaVuSans-Bold.ttf", 32), 
         'medium': ("DejaVuSans.ttf", 22), 'small': ("DejaVuSans.ttf", 18), 
         'tiny': ("DejaVuSans.ttf", 14), 'micro': ("DejaVuSans.ttf", 11)},
    ]
    
    for config in font_configs:
        try:
            for font_type, (font_name, size) in config.items():
                fonts[font_type] = ImageFont.truetype(font_name, size)
            print(f"Successfully loaded fonts: {list(config.keys())}")
            return fonts
        except (OSError, IOError):
            continue
    
    # Final fallback to default fonts
    print("Using default fonts as fallback")
    return {
        'title': ImageFont.load_default(),
        'large': ImageFont.load_default(),
        'medium': ImageFont.load_default(),
        'small': ImageFont.load_default(),
        'tiny': ImageFont.load_default(),
        'micro': ImageFont.load_default()
    }


def draw_radial_gradient(width, height, center_color, edge_color):
    """Create a radial gradient background"""
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    center_x, center_y = width // 2, height // 2
    max_radius = math.sqrt(center_x**2 + center_y**2)
    
    for y in range(height):
        for x in range(width):
            # Calculate distance from center
            distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
            ratio = min(distance / max_radius, 1.0)
            
            # Interpolate colors
            r = int(center_color[0] * (1 - ratio) + edge_color[0] * ratio)
            g = int(center_color[1] * (1 - ratio) + edge_color[1] * ratio)
            b = int(center_color[2] * (1 - ratio) + edge_color[2] * ratio)
            
            draw.point((x, y), fill=(r, g, b))
    
    return img


def draw_gradient_background(draw, width, height, color1, color2, vertical=False):
    """Draw a smooth gradient background with easing"""
    if vertical:
        for y in range(height):
            ratio = y / height
            # Easing function for smoother gradient
            ratio = ratio * ratio * (3 - 2 * ratio)
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.rectangle([0, y, width, y + 1], fill=(r, g, b))
    else:
        for x in range(width):
            ratio = x / width
            ratio = ratio * ratio * (3 - 2 * ratio)
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.rectangle([x, 0, x + 1, height], fill=(r, g, b))


def add_premium_patterns(draw, width, height):
    """Add sophisticated geometric patterns with holographic effect - simplified for minimalism"""
    # Subtle hexagonal pattern with reduced density and opacity
    hex_size = 80  # Larger size for less clutter
    pattern_color = (255, 255, 255, 4)  # Lower opacity
    
    for row in range(-1, height // hex_size + 2):
        for col in range(-1, width // hex_size + 2):
            if (row + col) % 2 == 0:  # Reduce density by half
                x = col * hex_size + (row % 2) * (hex_size // 2)
                y = row * hex_size * 0.866
                
                # Draw hexagon outline
                for i in range(6):
                    angle1 = math.radians(60 * i - 30)
                    angle2 = math.radians(60 * (i + 1) - 30)
                    x1 = x + hex_size * 0.4 * math.cos(angle1)
                    y1 = y + hex_size * 0.4 * math.sin(angle1)
                    x2 = x + hex_size * 0.4 * math.cos(angle2)
                    y2 = y + hex_size * 0.4 * math.sin(angle2)
                    draw.line([(x1, y1), (x2, y2)], fill=pattern_color, width=1)
    
    # Simplified flowing curves with lower opacity
    for i in range(0, width, 180):  # Wider spacing
        for j in range(2):  # Fewer curves
            curve_y = height * (0.4 + j * 0.3)
            curve_offset = math.sin(i / 150) * 20
            draw.arc(
                [i - 80, curve_y + curve_offset - 80, i + 80, curve_y + curve_offset + 80],
                0, 180, fill=(255, 255, 255, 4), width=1
            )


def add_holographic_shine(img):
    """Add holographic shine effect overlay - toned down for subtlety"""
    width, height = img.size
    shine = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shine)
    
    # Create fewer diagonal shine bands with softer colors
    for i in range(-height, width, 80):  # Wider spacing
        # Softer holographic colors
        colors = [
            (200, 150, 255, 8),  # Soft purple
            (150, 200, 255, 8),  # Soft cyan
            (255, 200, 150, 8),  # Soft orange
        ]
        color = colors[(i // 80) % len(colors)]
        
        points = [
            (i, 0),
            (i + 40, 0),
            (i + 40 - height, height),
            (i - height, height)
        ]
        draw.polygon(points, fill=color)
    
    # Blend with original
    img = Image.alpha_composite(img.convert('RGBA'), shine)
    return img


def create_glass_effect(draw, x, y, width, height, radius=20):
    """Create glass morphism effect panel - refined for better contrast"""
    # Semi-transparent background with higher opacity for readability
    draw.rounded_rectangle(
        [x, y, x + width, y + height],
        radius=radius,
        fill=(255, 255, 255, 24)
    )
    
    # Subtle top highlight
    draw.rounded_rectangle(
        [x, y, x + width, y + height // 4],
        radius=radius,
        fill=(255, 255, 255, 16)
    )
    
    # Softer border
    for i in range(2):
        alpha = 50 - i * 20
        draw.rounded_rectangle(
            [x - i, y - i, x + width + i, y + height + i],
            radius=radius + i,
            outline=(255, 255, 255, alpha),
            width=1
        )


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
    Generate the FRONT side of the digital ID card - PREMIUM EDITION
    
    Args:
        member: Member object
        base_url: Base URL for QR code (optional)
    
    Returns:
        Image: PIL Image object of the front card
    """
    # Standard ID card dimensions (1016x640 for high quality)
    CARD_WIDTH = 1016
    CARD_HEIGHT = 640
    
    # Improved color scheme - modern, appealing, high contrast
    # Inspired by tech themes: deep navy, vibrant teal, soft gold, neutrals
    COLOR_PRIMARY = (10, 30, 60)  # Deep navy
    COLOR_ACCENT = (0, 150, 180)  # Vibrant teal
    COLOR_ACCENT_LIGHT = (50, 180, 200)  # Lighter teal
    COLOR_HIGHLIGHT = (255, 200, 100)  # Soft gold
    BG_DARK = (15, 25, 40)  # Subtle dark background
    BG_DARKER = (5, 15, 30)  # Deeper for gradients
    TEXT_PRIMARY = (255, 255, 255)  # White for main text
    TEXT_SECONDARY = (200, 220, 240)  # Light blue-gray for secondary
    METALLIC_SILVER = (180, 180, 190)  # Softer silver
    
    # Create base with radial gradient for depth - softer transition
    img = draw_radial_gradient(CARD_WIDTH, CARD_HEIGHT, COLOR_PRIMARY, BG_DARKER)
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Add premium geometric patterns - simplified
    add_premium_patterns(draw, CARD_WIDTH, CARD_HEIGHT)
    
    # Load fonts
    fonts = load_fonts()
    
    # Premium header with glass morphism effect - simplified gradient
    header_height = 160
    header_gradient = Image.new('RGBA', (CARD_WIDTH, header_height), (0, 0, 0, 0))
    header_draw = ImageDraw.Draw(header_gradient)
    
    # Two-color gradient for cleaner look
    for i in range(header_height):
        ratio = i / header_height
        r = int(COLOR_ACCENT[0] * (1 - ratio) + COLOR_PRIMARY[0] * ratio)
        g = int(COLOR_ACCENT[1] * (1 - ratio) + COLOR_PRIMARY[1] * ratio)
        b = int(COLOR_ACCENT[2] * (1 - ratio) + COLOR_PRIMARY[2] * ratio)
        alpha = int(160 * (1 - ratio * 0.6))
        header_draw.rectangle([0, i, CARD_WIDTH, i+1], fill=(r, g, b, alpha))
    
    img.paste(header_gradient, (0, 0), header_gradient)
    
    # Load and add logo with subtle glow
    logo_path = os.path.join(current_app.root_path, 'static', 'DigitalClub_LOGO copy.svg')
    logo = load_and_process_logo(logo_path, (140, 140))
    
    if logo:
        # Subtle glow
        glow = logo.copy()
        glow = glow.filter(ImageFilter.GaussianBlur(8))
        # Position logo at top left
        img.paste(glow, (45, 25), glow)
        img.paste(logo, (50, 30), logo)
        
        # Add club name next to logo with better alignment and no shadow for minimalism
        club_y = 50
        draw.text((210, club_y), "DIGITAL CLUB", fill=TEXT_PRIMARY, font=fonts['title'])
        draw.text((210, club_y + 55), "Kampala International University in Tanzania", fill=TEXT_SECONDARY, font=fonts['small'])
    else:
        # Fallback text logo
        draw.text((50, 40), "DIGITAL CLUB", fill=COLOR_ACCENT, font=fonts['title'])
        draw.text((50, 95), "KIUT", fill=TEXT_SECONDARY, font=fonts['medium'])
    
    # Simplified corner accents - fewer layers
    corner_size = 80
    # Top right
    for i in range(2):
        offset = i * 20
        alpha = 60 - i * 20
        points = [
            (CARD_WIDTH - corner_size + offset, 0),
            (CARD_WIDTH, 0),
            (CARD_WIDTH, corner_size - offset)
        ]
        draw.polygon(points, fill=(*COLOR_ACCENT_LIGHT, alpha))
    
    # Bottom left
    for i in range(2):
        offset = i * 20
        alpha = 60 - i * 20
        points = [
            (0, CARD_HEIGHT - corner_size + offset),
            (0, CARD_HEIGHT),
            (corner_size - offset, CARD_HEIGHT)
        ]
        draw.polygon(points, fill=(*COLOR_ACCENT, alpha))
    
    # Fewer floating particles for cleaner design
    import random
    random.seed(42)
    for _ in range(15):  # Reduced from 30
        x = random.randint(0, CARD_WIDTH)
        y = random.randint(0, CARD_HEIGHT)
        size = random.randint(1, 2)
        alpha = random.randint(10, 40)
        draw.ellipse([x, y, x + size, y + size], fill=(255, 255, 255, alpha))
    
    # Add member photo with premium frame and subtle glow
    photo_size = 220
    photo_x = 50
    photo_y = 240
    
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
                
                # Subtle enhancement
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Brightness(profile_img)
                profile_img = enhancer.enhance(1.05)
                
                # Rounded mask
                mask = Image.new('L', (photo_size, photo_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, photo_size, photo_size], radius=25, fill=255)
                
                rounded_img = Image.new('RGB', (photo_size, photo_size), BG_DARK)
                rounded_img.paste(profile_img, (0, 0), mask)
                
                # Subtle glow
                for i in range(4, 0, -1):
                    alpha = 30 - i * 6
                    draw.rounded_rectangle(
                        [photo_x - i, photo_y - i, photo_x + photo_size + i, photo_y + photo_size + i],
                        radius=25 + i,
                        fill=(*COLOR_ACCENT_LIGHT, alpha)
                    )
                
                # Paste photo
                img.paste(rounded_img, (photo_x, photo_y))
                
                # Simplified border - fewer layers
                for i in range(2):
                    offset = i * 2
                    alpha = 200 - i * 80
                    border_color = COLOR_ACCENT if i % 2 == 0 else COLOR_ACCENT_LIGHT
                    draw.rounded_rectangle(
                        [photo_x - offset, photo_y - offset, photo_x + photo_size + offset, photo_y + photo_size + offset],
                        radius=25 + offset,
                        outline=(*border_color, alpha),
                        width=1
                    )
                
                # Simplified corner accents
                accent_size = 15
                accent_alpha = 180
                # Top-left
                draw.rectangle([photo_x - 3, photo_y - 3, photo_x - 3 + accent_size, photo_y - 3 + 2], 
                               fill=(*COLOR_HIGHLIGHT, accent_alpha))
                draw.rectangle([photo_x - 3, photo_y - 3, photo_x - 3 + 2, photo_y - 3 + accent_size], 
                               fill=(*COLOR_HIGHLIGHT, accent_alpha))
                
                # Top-right
                draw.rectangle([photo_x + photo_size + 3 - accent_size, photo_y - 3, photo_x + photo_size + 3, photo_y - 3 + 2], 
                               fill=(*COLOR_HIGHLIGHT, accent_alpha))
                draw.rectangle([photo_x + photo_size + 1, photo_y - 3, photo_x + photo_size + 3, photo_y - 3 + accent_size], 
                               fill=(*COLOR_HIGHLIGHT, accent_alpha))
                
                # Bottom-left
                draw.rectangle([photo_x - 3, photo_y + photo_size + 1, photo_x - 3 + accent_size, photo_y + photo_size + 3], 
                               fill=(*COLOR_HIGHLIGHT, accent_alpha))
                draw.rectangle([photo_x - 3, photo_y + photo_size + 3 - accent_size, photo_x - 3 + 2, photo_y + photo_size + 3], 
                               fill=(*COLOR_HIGHLIGHT, accent_alpha))
                
                # Bottom-right
                draw.rectangle([photo_x + photo_size + 3 - accent_size, photo_y + photo_size + 1, photo_x + photo_size + 3, photo_y + photo_size + 3], 
                               fill=(*COLOR_HIGHLIGHT, accent_alpha))
                draw.rectangle([photo_x + photo_size + 1, photo_y + photo_size + 3 - accent_size, photo_x + photo_size + 3, photo_y + photo_size + 3], 
                               fill=(*COLOR_HIGHLIGHT, accent_alpha))
            else:
                # Placeholder
                create_glass_effect(draw, photo_x, photo_y, photo_size, photo_size, 25)
                draw.text((photo_x + 85, photo_y + 85), "📷", font=fonts['title'])
        else:
            # Placeholder
            create_glass_effect(draw, photo_x, photo_y, photo_size, photo_size, 25)
            draw.text((photo_x + 85, photo_y + 85), "📷", font=fonts['title'])
    except Exception as e:
        # Placeholder on error
        create_glass_effect(draw, photo_x, photo_y, photo_size, photo_size, 25)
        draw.text((photo_x + 85, photo_y + 85), "📷", font=fonts['title'])
    
    # Member information with premium glass panel - better spacing
    info_x = 330
    info_y = 195
    panel_width = CARD_WIDTH - info_x - 45
    panel_height = 420
    
    # Glass effect
    create_glass_effect(draw, info_x - 25, info_y - 25, panel_width, panel_height, 25)
    
    # Subtle inner border
    draw.rounded_rectangle(
        [info_x - 25, info_y - 25, info_x + panel_width - 25, info_y + panel_height - 25],
        radius=25,
        outline=(*COLOR_ACCENT_LIGHT, 20),
        width=1
    )
    
    # Member name with better hierarchy
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
        draw.text((info_x, info_y + i * 48), line, fill=TEXT_PRIMARY, font=fonts['large'])
    
    info_y += len(name_lines) * 48 + 30  # Increased spacing
    
    # Simplified separator
    draw.line([(info_x, info_y), (info_x + panel_width - 50, info_y)], fill=(*COLOR_ACCENT, 100), width=1)
    info_y += 25
    
    # Member ID with cleaner badge
    id_badge_width = panel_width - 30
    id_badge_height = 80
    id_badge = Image.new('RGBA', (id_badge_width, id_badge_height), (0, 0, 0, 0))
    id_draw = ImageDraw.Draw(id_badge)
    for i in range(id_badge_height):
        ratio = i / id_badge_height
        alpha = int(40 * (1 - ratio * 0.4))
        id_draw.rectangle([0, i, id_badge_width, i+1], fill=(*COLOR_ACCENT_LIGHT, alpha))
    img.paste(id_badge, (info_x, info_y), id_badge)
    
    draw.text((info_x + 10, info_y + 8), "MEMBER ID", fill=COLOR_ACCENT, font=fonts['tiny'])
    draw.text((info_x + 10, info_y + 28), member.member_id_number, fill=COLOR_HIGHLIGHT, font=fonts['large'])
    info_y += 95
    
    # Course and Year with better alignment
    if member.course:
        draw.text((info_x, info_y), "COURSE", fill=COLOR_ACCENT, font=fonts['tiny'])
        info_y += 22
        course_text = member.course[:28]
        draw.text((info_x, info_y), course_text, fill=TEXT_PRIMARY, font=fonts['small'])
        info_y += 40  # Increased spacing
    
    if member.year:
        draw.text((info_x, info_y), "ACADEMIC YEAR", fill=COLOR_ACCENT, font=fonts['tiny'])
        info_y += 22
        draw.text((info_x, info_y), member.year, fill=TEXT_PRIMARY, font=fonts['small'])
        info_y += 40
    
    # Status badge - simplified
    status_text = member.status.upper()
    status_color = COLOR_ACCENT if member.status == 'student' else COLOR_HIGHLIGHT
    
    badge_width = 160
    badge_height = 42
    badge_x = info_x
    badge_y = info_y + 15
    
    # Subtle glow
    draw.rounded_rectangle(
        [badge_x - 2, badge_y - 2, badge_x + badge_width + 2, badge_y + badge_height + 2],
        radius=21 + 2,
        fill=(*status_color, 20)
    )
    
    # Badge background
    badge_img = Image.new('RGBA', (badge_width, badge_height), (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge_img)
    for i in range(badge_height):
        ratio = i / badge_height
        alpha = int(50 * (1 - ratio * 0.2))
        badge_draw.rectangle([0, i, badge_width, i+1], fill=(*status_color, alpha))
    img.paste(badge_img, (badge_x, badge_y), badge_img)
    
    # Badge border
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
        radius=21,
        outline=status_color,
        width=2
    )
    
    # Badge text
    text_x = badge_x + (badge_width - len(status_text) * 12) // 2
    draw.text((text_x, badge_y + 8), status_text, fill=TEXT_PRIMARY, font=fonts['medium'])
    
    # Generate QR code with simpler frame
    if not base_url:
        try:
            base_url = 'https://databd.auriumlabs.com' #request.url_root.rstrip('/')
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
    
    qr_img = qr.make_image(fill_color=BG_DARK, back_color=TEXT_PRIMARY)
    qr_img = qr_img.resize((150, 150), Image.Resampling.LANCZOS)
    
    # QR position
    qr_x = CARD_WIDTH - 350
    qr_y = CARD_HEIGHT - 290
    qr_size = 150
    
    # Subtle glow
    draw.rounded_rectangle(
        [qr_x - 15, qr_y - 15, qr_x + qr_size + 15, qr_y + qr_size + 15],
        radius=18,
        fill=(*COLOR_ACCENT_LIGHT, 30)
    )
    
    # Simple frame
    frame_padding = 12
    qr_frame = Image.new('RGBA', (qr_size + frame_padding*2, qr_size + frame_padding*2), (0, 0, 0, 0))
    qr_frame_draw = ImageDraw.Draw(qr_frame)
    
    for i in range(qr_size + frame_padding*2):
        ratio = i / (qr_size + frame_padding*2)
        r = int(240 * (1 - ratio * 0.05))
        qr_frame_draw.rectangle([0, i, qr_size + frame_padding*2, i+1], fill=(r, r, r, 200))
    
    img.paste(qr_frame, (qr_x - frame_padding, qr_y - frame_padding), qr_frame)
    
    # Paste QR
    img.paste(qr_img, (qr_x, qr_y))
    
    # Simplified border
    draw.rounded_rectangle(
        [qr_x - frame_padding, qr_y - frame_padding, 
         qr_x + qr_size + frame_padding, qr_y + qr_size + frame_padding],
        radius=15,
        outline=(*COLOR_ACCENT, 180),
        width=1
    )
    
    # Simplified corner accents
    accent_len = 20
    accent_alpha = 200
    # Top-left
    draw.rectangle([qr_x - frame_padding - 4, qr_y - frame_padding - 4, 
                    qr_x - frame_padding - 4 + accent_len, qr_y - frame_padding - 4 + 2], 
                   fill=(*COLOR_HIGHLIGHT, accent_alpha))
    draw.rectangle([qr_x - frame_padding - 4, qr_y - frame_padding - 4, 
                    qr_x - frame_padding - 4 + 2, qr_y - frame_padding - 4 + accent_len], 
                   fill=(*COLOR_HIGHLIGHT, accent_alpha))
    
    # Top-right
    draw.rectangle([qr_x + qr_size + frame_padding + 4 - accent_len, qr_y - frame_padding - 4, 
                    qr_x + qr_size + frame_padding + 4, qr_y - frame_padding - 4 + 2], 
                   fill=(*COLOR_HIGHLIGHT, accent_alpha))
    draw.rectangle([qr_x + qr_size + frame_padding + 2, qr_y - frame_padding - 4, 
                    qr_x + qr_size + frame_padding + 4, qr_y - frame_padding - 4 + accent_len], 
                   fill=(*COLOR_HIGHLIGHT, accent_alpha))
    
    # Bottom-left
    draw.rectangle([qr_x - frame_padding - 4, qr_y + qr_size + frame_padding + 2, 
                    qr_x - frame_padding - 4 + accent_len, qr_y + qr_size + frame_padding + 4], 
                   fill=(*COLOR_HIGHLIGHT, accent_alpha))
    draw.rectangle([qr_x - frame_padding - 4, qr_y + qr_size + frame_padding + 4 - accent_len, 
                    qr_x - frame_padding - 4 + 2, qr_y + qr_size + frame_padding + 4], 
                   fill=(*COLOR_HIGHLIGHT, accent_alpha))
    
    # Bottom-right
    draw.rectangle([qr_x + qr_size + frame_padding + 4 - accent_len, qr_y + qr_size + frame_padding + 2, 
                    qr_x + qr_size + frame_padding + 4, qr_y + qr_size + frame_padding + 4], 
                   fill=(*COLOR_HIGHLIGHT, accent_alpha))
    draw.rectangle([qr_x + qr_size + frame_padding + 2, qr_y + qr_size + frame_padding + 4 - accent_len, 
                    qr_x + qr_size + frame_padding + 4, qr_y + qr_size + frame_padding + 4], 
                   fill=(*COLOR_HIGHLIGHT, accent_alpha))
    
    # QR label
    label_text = "SCAN TO VERIFY"
    label_x = qr_x - frame_padding + 45
    label_y = qr_y + qr_size + frame_padding + 18
    draw.text((label_x, label_y), label_text, fill=TEXT_SECONDARY, font=fonts['micro'])
    
    # Validity information - simplified
    if member.created_at:
        valid_x = 50
        valid_y = CARD_HEIGHT - 150
        valid_width = 200
        valid_height = 100
        
        create_glass_effect(draw, valid_x, valid_y, valid_width, valid_height, 15)
        
        draw.text((valid_x + 15, valid_y + 15), "VALID FROM", fill=COLOR_ACCENT, font=fonts['tiny'])
        valid_from = member.created_at.strftime('%B %Y')
        draw.text((valid_x + 15, valid_y + 35), valid_from, fill=TEXT_PRIMARY, font=fonts['small'])
        
        draw.text((valid_x + 15, valid_y + 62), "STATUS", fill=COLOR_ACCENT, font=fonts['tiny'])
        draw.text((valid_x + 15, valid_y + 77), "● ACTIVE", fill=COLOR_ACCENT_LIGHT, font=fonts['tiny'])
    
    # Bottom accent - simplified wave
    accent_height = 20
    holographic_accent = Image.new('RGBA', (CARD_WIDTH, accent_height), (0, 0, 0, 0))
    holo_draw = ImageDraw.Draw(holographic_accent)
    
    for x in range(CARD_WIDTH):
        ratio = (x / CARD_WIDTH) * 2 * math.pi
        wave = (math.sin(ratio * 2) + 1) / 2  # Smoother wave
        color = COLOR_ACCENT_LIGHT
        alpha = int(60 * wave)
        holo_draw.line([(x, 0), (x, accent_height)], fill=(*color, alpha))
    
    img.paste(holographic_accent, (0, CARD_HEIGHT - accent_height), holographic_accent)
    
    # Apply holographic shine - toned down
    img = add_holographic_shine(img)
    
    # Convert back to RGB
    if img.mode == 'RGBA':
        bg = Image.new('RGB', img.size, (15, 25, 40))
        bg.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
        img = bg
    
    return img


def generate_digital_id_back(member, base_url=None):
    """
    Generate the BACK side of the digital ID card - PREMIUM EDITION
    
    Args:
        member: Member object
        base_url: Base URL for QR code (optional)
    
    Returns:
        Image: PIL Image object of the back card
    """
    # Standard ID card dimensions
    CARD_WIDTH = 1016
    CARD_HEIGHT = 640
    
    # Improved color scheme matching front
    COLOR_PRIMARY = (10, 30, 60)
    COLOR_ACCENT = (0, 150, 180)
    COLOR_ACCENT_LIGHT = (50, 180, 200)
    COLOR_HIGHLIGHT = (255, 200, 100)
    BG_DARK = (15, 25, 40)
    BG_DARKER = (5, 15, 30)
    TEXT_PRIMARY = (255, 255, 255)
    TEXT_SECONDARY = (200, 220, 240)
    
    # Base gradient
    img = draw_radial_gradient(CARD_WIDTH, CARD_HEIGHT, BG_DARK, BG_DARKER)
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Subtle diagonal overlay
    overlay = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for i in range(CARD_WIDTH + CARD_HEIGHT):
        ratio = i / (CARD_WIDTH + CARD_HEIGHT)
        alpha = int(30 * (1 - ratio))
        for x in range(max(0, i - CARD_HEIGHT), min(CARD_WIDTH, i)):
            y = i - x
            if 0 <= y < CARD_HEIGHT:
                overlay_draw.point((x, y), fill=(*COLOR_PRIMARY, alpha))
    img.paste(overlay, (0, 0), overlay)
    
    # Premium patterns - simplified
    add_premium_patterns(draw, CARD_WIDTH, CARD_HEIGHT)
    
    # Fonts
    fonts = load_fonts()
    
    # Header gradient - simplified
    header_height = 120
    header_gradient = Image.new('RGBA', (CARD_WIDTH, header_height), (0, 0, 0, 0))
    header_draw = ImageDraw.Draw(header_gradient)
    
    for i in range(header_height):
        ratio = i / header_height
        r = int(COLOR_ACCENT[0] * (1 - ratio) + COLOR_PRIMARY[0] * ratio)
        g = int(COLOR_ACCENT[1] * (1 - ratio) + COLOR_PRIMARY[1] * ratio)
        b = int(COLOR_ACCENT[2] * (1 - ratio) + COLOR_PRIMARY[2] * ratio)
        alpha = int(100 * (1 - ratio * 0.5))
        header_draw.rectangle([0, i, CARD_WIDTH, i+1], fill=(r, g, b, alpha))
    
    img.paste(header_gradient, (0, 0), header_gradient)
    
    # Logo at top center with subtle glow
    logo_path = os.path.join(current_app.root_path, 'static', 'DigitalClub_LOGO copy.svg')
    logo = load_and_process_logo(logo_path, (100, 100))
    
    if logo:
        glow = logo.copy()
        glow = glow.filter(ImageFilter.GaussianBlur(6))
        logo_x = CARD_WIDTH // 2 - 50
        img.paste(glow, (logo_x - 3, 15), glow)
        img.paste(logo, (logo_x, 20), logo)
    
    # Simplified separator
    separator_y = 130
    draw.line([(80, separator_y), (CARD_WIDTH - 80, separator_y)], fill=(*COLOR_ACCENT, 80), width=1)
    
    # Content panels - better spacing and alignment
    left_x = 60
    right_x = CARD_WIDTH // 2 + 30
    content_y = 160
    panel_width = (CARD_WIDTH // 2) - 90
    
    # Left panel - About
    left_panel_height = 180
    create_glass_effect(draw, left_x, content_y, panel_width, left_panel_height, 20)
    
    draw.text((left_x + 20, content_y + 15), "ABOUT THE CLUB", fill=COLOR_ACCENT_LIGHT, font=fonts['medium'])
    
    about_text = [
        "The Digital Club is a vibrant community of tech enthusiasts,",
        "developers, and innovators at KIUT.",
        # "",
        "We foster learning, collaboration and innovation in technology."
    ]
    
    about_y = content_y + 50
    for line in about_text:
        if line:
            draw.text((left_x + 20, about_y), line, fill=TEXT_SECONDARY, font=fonts['tiny'])
        about_y += 22  # Adjusted spacing
    
    # Contact panel
    contact_y = content_y + left_panel_height + 30  # Increased spacing
    contact_height = 140
    create_glass_effect(draw, left_x, contact_y, panel_width, contact_height, 20)
    
    draw.text((left_x + 20, contact_y + 15), "CONTACT INFO", fill=COLOR_ACCENT_LIGHT, font=fonts['medium'])
    
    contact_info = [
        ("📧", "info@digitalclub.kiut.ac.tz"),
        ("🌐", "www.digitalclub.kiut.ac.tz"),
        ("📱", "+254 XXX XXX XXX")
    ]
    
    contact_text_y = contact_y + 50
    for icon, text in contact_info:
        draw.text((left_x + 20, contact_text_y), icon, font=fonts['small'])
        draw.text((left_x + 40, contact_text_y), text, fill=TEXT_SECONDARY, font=fonts['tiny'])
        contact_text_y += 30
    
    # Right panel - Terms
    terms_panel_height = 180
    create_glass_effect(draw, right_x, content_y, panel_width, terms_panel_height, 20)
    
    draw.text((right_x + 20, content_y + 15), "TERMS & CONDITIONS", fill=COLOR_ACCENT_LIGHT, font=fonts['medium'])
    
    terms = [
        "• This card is non-transferable",
        "• Valid for current members only",
        "• Must be presented at events",
        "• Report if lost or stolen",
        # "• Subject to club regulations",
        "• Expires upon graduation"
    ]
    
    terms_text_y = content_y + 50
    for term in terms:
        draw.text((right_x + 20, terms_text_y), term, fill=TEXT_SECONDARY, font=fonts['tiny'])
        terms_text_y += 24  # Adjusted
    
    # Security panel
    security_y = content_y + terms_panel_height + 30
    security_height = 140
    create_glass_effect(draw, right_x, security_y, panel_width, security_height, 20)
    
    draw.text((right_x + 20, security_y + 15), "SECURITY FEATURES", fill=COLOR_ACCENT_LIGHT, font=fonts['medium'])
    
    security_features = [
        "✓ Holographic elements",
        "✓ QR code verification",
        "✓ Unique member ID",
        "✓ Digital signature"
    ]
    
    security_text_y = security_y + 50
    for feature in security_features:
        draw.text((right_x + 20, security_text_y), feature, fill=TEXT_SECONDARY, font=fonts['tiny'])
        security_text_y += 24
    
    # Signature line - simplified
    sig_y = CARD_HEIGHT - 130
    sig_line_start = 100
    sig_line_end = 380
    
    # draw.text((sig_line_start, sig_y - 20), "AUTHORIZED SIGNATURE", fill=COLOR_ACCENT, font=fonts['micro'])
    # draw.line([(sig_line_start, sig_y), (sig_line_end, sig_y)], 
    #           fill=(*TEXT_SECONDARY, 150), width=1)
    
    # Magnetic strip - softer
    strip_y = CARD_HEIGHT - 75
    strip_height = 60
    
    strip_img = Image.new('RGBA', (CARD_WIDTH, strip_height), (0, 0, 0, 0))
    strip_draw = ImageDraw.Draw(strip_img)
    for i in range(strip_height):
        ratio = i / strip_height
        darkness = int(25 + 20 * math.sin(ratio * math.pi))
        alpha = 180
        strip_draw.rectangle([0, i, CARD_WIDTH, i+1], fill=(darkness, darkness, darkness + 5, alpha))
    
    # Fewer holographic lines
    for x in range(0, CARD_WIDTH, 30):
        line_alpha = 30
        strip_draw.line([(x, 0), (x, strip_height)], fill=(100, 150, 200, line_alpha), width=1)
    
    img.paste(strip_img, (0, strip_y), strip_img)
    
    # Footer
    footer_y = CARD_HEIGHT - 95
    footer_text = f"© {member.created_at.year if member.created_at else '2024'} KIUT DIGITAL CLUB  •  ALL RIGHTS RESERVED"
    footer_x = CARD_WIDTH // 2 - len(footer_text) * 3
    draw.text((footer_x, footer_y), footer_text, fill=TEXT_SECONDARY, font=fonts['micro'])
    
    # Simplified corner accents
    corner_size = 80
    # Top right
    for i in range(2):
        offset = i * 20
        alpha = 60 - i * 20
        points = [
            (CARD_WIDTH - corner_size + offset, 0),
            (CARD_WIDTH, 0),
            (CARD_WIDTH, corner_size - offset)
        ]
        draw.polygon(points, fill=(*COLOR_ACCENT_LIGHT, alpha))
    
    # Bottom left
    for i in range(2):
        offset = i * 20
        alpha = 60 - i * 20
        points = [
            (0, CARD_HEIGHT - corner_size + offset),
            (0, CARD_HEIGHT),
            (corner_size - offset, CARD_HEIGHT)
        ]
        draw.polygon(points, fill=(*COLOR_ACCENT, alpha))
    
    # Holographic shine
    img = add_holographic_shine(img)
    
    # Convert to RGB
    if img.mode == 'RGBA':
        bg = Image.new('RGB', img.size, (15, 25, 40))
        bg.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
        img = bg
    
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