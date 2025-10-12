"""
Digital ID Card Generator - Premium Edition
Generates stunning, premium-quality digital ID cards with advanced visual effects
Features: Glass morphism, holographic accents, depth effects, modern design
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
    try:
        return {
            'title': ImageFont.truetype("arialbd.ttf", 48),  # Bold
            'large': ImageFont.truetype("arialbd.ttf", 32),  # Bold
            'medium': ImageFont.truetype("arial.ttf", 22),
            'small': ImageFont.truetype("arial.ttf", 18),
            'tiny': ImageFont.truetype("arial.ttf", 14),
            'micro': ImageFont.truetype("arial.ttf", 11)
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
    """Add sophisticated geometric patterns with holographic effect"""
    # Hexagonal pattern
    hex_size = 60
    pattern_color_1 = (255, 255, 255, 8)
    pattern_color_2 = (100, 200, 255, 12)
    
    for row in range(-1, height // hex_size + 2):
        for col in range(-1, width // hex_size + 2):
            x = col * hex_size + (row % 2) * (hex_size // 2)
            y = row * hex_size * 0.866
            
            # Draw hexagon outline
            color = pattern_color_1 if (row + col) % 2 == 0 else pattern_color_2
            for i in range(6):
                angle1 = math.radians(60 * i - 30)
                angle2 = math.radians(60 * (i + 1) - 30)
                x1 = x + hex_size * 0.4 * math.cos(angle1)
                y1 = y + hex_size * 0.4 * math.sin(angle1)
                x2 = x + hex_size * 0.4 * math.cos(angle2)
                y2 = y + hex_size * 0.4 * math.sin(angle2)
                draw.line([(x1, y1), (x2, y2)], fill=color, width=1)
    
    # Add flowing curves for depth
    for i in range(0, width, 120):
        for j in range(3):
            curve_y = height * (0.3 + j * 0.2)
            curve_offset = math.sin(i / 100) * 30
            draw.arc(
                [i - 60, curve_y + curve_offset - 60, i + 60, curve_y + curve_offset + 60],
                0, 180, fill=(255, 255, 255, 6), width=2
            )


def add_holographic_shine(img):
    """Add holographic shine effect overlay"""
    width, height = img.size
    shine = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shine)
    
    # Create diagonal shine bands
    for i in range(-height, width, 40):
        # Rainbow holographic colors
        colors = [
            (255, 100, 200, 15),  # Pink
            (100, 200, 255, 15),  # Cyan
            (200, 255, 100, 15),  # Yellow-green
            (255, 200, 100, 15),  # Orange
        ]
        color = colors[(i // 40) % len(colors)]
        
        points = [
            (i, 0),
            (i + 20, 0),
            (i + 20 - height, height),
            (i - height, height)
        ]
        draw.polygon(points, fill=color)
    
    # Blend with original
    img = Image.alpha_composite(img.convert('RGBA'), shine)
    return img


def create_glass_effect(draw, x, y, width, height, radius=20):
    """Create glass morphism effect panel"""
    # Semi-transparent background
    draw.rounded_rectangle(
        [x, y, x + width, y + height],
        radius=radius,
        fill=(255, 255, 255, 12)
    )
    
    # Top highlight for glass effect
    draw.rounded_rectangle(
        [x, y, x + width, y + height // 3],
        radius=radius,
        fill=(255, 255, 255, 20)
    )
    
    # Border with gradient effect
    for i in range(2):
        alpha = 60 - i * 20
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
    
    # Premium color scheme - enhanced with metallics
    COLOR_BLUE = (25, 118, 210)  # Deeper blue
    COLOR_BLUE_LIGHT = (66, 165, 245)  # Lighter accent
    COLOR_GREEN = (46, 213, 115)  # Vibrant green
    COLOR_GREEN_DARK = (39, 174, 96)  # Darker green
    COLOR_CYAN = (0, 184, 212)  # Cyan accent
    COLOR_PURPLE = (103, 58, 183)  # Purple accent
    BG_DARK = (10, 15, 35)  # Deeper dark
    BG_DARKER = (5, 10, 25)
    TEXT_WHITE = (255, 255, 255)
    TEXT_LIGHT = (220, 230, 245)
    TEXT_GOLD = (255, 215, 0)
    METALLIC_SILVER = (192, 192, 192)
    
    # Create base with radial gradient for depth
    img = draw_radial_gradient(CARD_WIDTH, CARD_HEIGHT, COLOR_BLUE, BG_DARKER)
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Add premium geometric patterns
    add_premium_patterns(draw, CARD_WIDTH, CARD_HEIGHT)
    
    # Load fonts
    fonts = load_fonts()
    
    # Premium header with glass morphism effect
    header_height = 160
    header_gradient = Image.new('RGBA', (CARD_WIDTH, header_height), (0, 0, 0, 0))
    header_draw = ImageDraw.Draw(header_gradient)
    
    # Multi-color gradient header
    for i in range(header_height):
        ratio = i / header_height
        # Mix between green and cyan
        r = int(COLOR_GREEN[0] * (1 - ratio) + COLOR_CYAN[0] * ratio)
        g = int(COLOR_GREEN[1] * (1 - ratio) + COLOR_CYAN[1] * ratio)
        b = int(COLOR_GREEN[2] * (1 - ratio) + COLOR_CYAN[2] * ratio)
        alpha = int(180 * (1 - ratio * 0.8))
        header_draw.rectangle([0, i, CARD_WIDTH, i+1], fill=(r, g, b, alpha))
    
    img.paste(header_gradient, (0, 0), header_gradient)
    
    # Load and add logo with glow effect
    logo_path = os.path.join(current_app.root_path, 'static', 'DigitalClub_LOGO copy.svg')
    logo = load_and_process_logo(logo_path, (140, 140))
    
    if logo:
        # Create glow effect for logo
        glow = logo.copy()
        for _ in range(3):
            glow = glow.filter(ImageFilter.GaussianBlur(10))
        # Position logo at top left with glow
        img.paste(glow, (45, 25), glow)
        img.paste(logo, (50, 30), logo)
        
        # Add club name next to logo with shadow
        club_y = 50
        # Shadow
        draw.text((210, club_y + 2), "DIGITAL CLUB", fill=(0, 0, 0, 150), font=fonts['title'])
        # Main text with gradient effect
        draw.text((208, club_y), "DIGITAL CLUB", fill=TEXT_WHITE, font=fonts['title'])
        draw.text((208, club_y + 55), "Kampala International University in Tanzania", fill=TEXT_LIGHT, font=fonts['small'])
    else:
        # Fallback text logo
        draw.text((50, 40), "DIGITAL CLUB", fill=COLOR_GREEN, font=fonts['title'])
        draw.text((50, 95), "KIUT", fill=TEXT_LIGHT, font=fonts['medium'])
    
    # Premium corner accents with glow
    corner_size = 80
    # Top right - geometric design
    for i in range(3):
        offset = i * 15
        alpha = 80 - i * 20
        points = [
            (CARD_WIDTH - corner_size + offset, 0),
            (CARD_WIDTH, 0),
            (CARD_WIDTH, corner_size - offset)
        ]
        draw.polygon(points, fill=(*COLOR_GREEN, alpha))
    
    # Bottom left - geometric design
    for i in range(3):
        offset = i * 15
        alpha = 80 - i * 20
        points = [
            (0, CARD_HEIGHT - corner_size + offset),
            (0, CARD_HEIGHT),
            (corner_size - offset, CARD_HEIGHT)
        ]
        draw.polygon(points, fill=(*COLOR_CYAN, alpha))
    
    # Add floating particles effect for premium feel
    import random
    random.seed(42)  # Consistent pattern
    for _ in range(30):
        x = random.randint(0, CARD_WIDTH)
        y = random.randint(0, CARD_HEIGHT)
        size = random.randint(1, 3)
        alpha = random.randint(20, 60)
        draw.ellipse([x, y, x + size, y + size], fill=(255, 255, 255, alpha))
    
    # Add member photo with premium frame and glow
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
                
                # Enhance photo with subtle brightness boost
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Brightness(profile_img)
                profile_img = enhancer.enhance(1.1)
                
                # Create rounded rectangle mask
                mask = Image.new('L', (photo_size, photo_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, photo_size, photo_size], radius=25, fill=255)
                
                # Create rounded image
                rounded_img = Image.new('RGB', (photo_size, photo_size), BG_DARK)
                rounded_img.paste(profile_img, (0, 0), mask)
                
                # Add glow effect behind photo
                for i in range(8, 0, -1):
                    alpha = 40 - i * 4
                    draw.rounded_rectangle(
                        [photo_x-i*2, photo_y-i*2, photo_x+photo_size+i*2, photo_y+photo_size+i*2],
                        radius=25+i*2,
                        fill=(*COLOR_GREEN, alpha)
                    )
                
                # Paste photo
                img.paste(rounded_img, (photo_x, photo_y))
                
                # Multi-layer premium border
                for i in range(4):
                    offset = i * 2
                    alpha = 255 - i * 40
                    border_color = COLOR_GREEN if i % 2 == 0 else COLOR_CYAN
                    draw.rounded_rectangle(
                        [photo_x-offset, photo_y-offset, photo_x+photo_size+offset, photo_y+photo_size+offset],
                        radius=25+offset,
                        outline=(*border_color, alpha),
                        width=2
                    )
                
                # Add corner accent decorations
                accent_size = 20
                for corner in [(photo_x-5, photo_y-5), (photo_x+photo_size-15, photo_y-5),
                              (photo_x-5, photo_y+photo_size-15), (photo_x+photo_size-15, photo_y+photo_size-15)]:
                    draw.rectangle([corner[0], corner[1], corner[0]+accent_size, corner[1]+3], 
                                 fill=(*TEXT_GOLD, 200))
                    draw.rectangle([corner[0], corner[1], corner[0]+3, corner[1]+accent_size], 
                                 fill=(*TEXT_GOLD, 200))
            else:
                # Premium placeholder
                create_glass_effect(draw, photo_x, photo_y, photo_size, photo_size, 25)
                draw.text((photo_x + 85, photo_y + 85), "📷", font=fonts['title'])
        else:
            # Premium placeholder
            create_glass_effect(draw, photo_x, photo_y, photo_size, photo_size, 25)
            draw.text((photo_x + 85, photo_y + 85), "📷", font=fonts['title'])
    except Exception as e:
        # Premium placeholder on error
        create_glass_effect(draw, photo_x, photo_y, photo_size, photo_size, 25)
        draw.text((photo_x + 85, photo_y + 85), "📷", font=fonts['title'])
    
    # Add member information with premium glass panel
    info_x = 330
    info_y = 195
    panel_width = CARD_WIDTH - info_x - 45
    panel_height = 420
    
    # Premium glass morphism info panel
    create_glass_effect(draw, info_x - 25, info_y - 25, panel_width, panel_height, 25)
    
    # Add subtle inner glow
    for i in range(3):
        alpha = 30 - i * 8
        draw.rounded_rectangle(
            [info_x - 25 + i, info_y - 25 + i, info_x + panel_width - 25 - i, info_y + panel_height - 25 - i],
            radius=25 - i,
            outline=(*COLOR_GREEN, alpha),
            width=1
        )
    
    # Member name with shadow and glow
    name_lines = []
    name = member.full_name.upper()
    if len(name) > 18:
        words = name.split()
        line1 = []
        line2 = []
        for word in words:
            if len(' '.join(line1 + [word])) <= 18:
                line1.append(word)
            else:
                line2.append(word)
        name_lines.append(' '.join(line1))
        if line2:
            name_lines.append(' '.join(line2))
    else:
        name_lines.append(name)
    
    for i, line in enumerate(name_lines):
        # Shadow
        draw.text((info_x + 2, info_y + i * 48 + 2), line, fill=(0, 0, 0, 150), font=fonts['large'])
        # Main text
        draw.text((info_x, info_y + i * 48), line, fill=TEXT_WHITE, font=fonts['large'])
        # Subtle glow
        draw.text((info_x, info_y + i * 48), line, fill=(*COLOR_GREEN, 30), font=fonts['large'])
    
    info_y += len(name_lines) * 48 + 25
    
    # Premium separator with gradient
    separator_gradient = Image.new('RGBA', (panel_width - 30, 3), (0, 0, 0, 0))
    sep_draw = ImageDraw.Draw(separator_gradient)
    for x in range(panel_width - 30):
        ratio = x / (panel_width - 30)
        alpha = int(255 * math.sin(ratio * math.pi))
        sep_draw.line([(x, 0), (x, 3)], fill=(*COLOR_GREEN, alpha))
    img.paste(separator_gradient, (info_x, info_y), separator_gradient)
    info_y += 20
    
    # Member ID with premium badge
    id_badge_width = panel_width - 30
    id_badge_height = 80
    # Create gradient background for ID
    id_badge = Image.new('RGBA', (id_badge_width, id_badge_height), (0, 0, 0, 0))
    id_draw = ImageDraw.Draw(id_badge)
    for i in range(id_badge_height):
        ratio = i / id_badge_height
        alpha = int(60 * (1 - ratio * 0.5))
        id_draw.rectangle([0, i, id_badge_width, i+1], fill=(*COLOR_BLUE_LIGHT, alpha))
    img.paste(id_badge, (info_x, info_y), id_badge)
    
    draw.text((info_x + 10, info_y + 8), "MEMBER ID", fill=COLOR_CYAN, font=fonts['tiny'])
    # Shadow for ID
    draw.text((info_x + 12, info_y + 30), member.member_id_number, fill=(0, 0, 0, 120), font=fonts['large'])
    # Main ID with gradient effect
    draw.text((info_x + 10, info_y + 28), member.member_id_number, fill=TEXT_GOLD, font=fonts['large'])
    info_y += 95
    
    # Course and Year in modern cards
    if member.course:
        # Course card
        draw.text((info_x, info_y), "COURSE", fill=COLOR_CYAN, font=fonts['tiny'])
        info_y += 22
        course_text = member.course[:28]  # Limit length
        # Shadow
        draw.text((info_x + 1, info_y + 1), course_text, fill=(0, 0, 0, 100), font=fonts['small'])
        draw.text((info_x, info_y), course_text, fill=TEXT_WHITE, font=fonts['small'])
        info_y += 38
    
    if member.year:
        draw.text((info_x, info_y), "ACADEMIC YEAR", fill=COLOR_CYAN, font=fonts['tiny'])
        info_y += 22
        # Shadow
        draw.text((info_x + 1, info_y + 1), member.year, fill=(0, 0, 0, 100), font=fonts['small'])
        draw.text((info_x, info_y), member.year, fill=TEXT_WHITE, font=fonts['small'])
        info_y += 38
    
    # Premium status badge with glow
    status_text = member.status.upper()
    status_color = COLOR_GREEN if member.status == 'student' else TEXT_GOLD
    
    badge_width = 160
    badge_height = 42
    badge_x = info_x
    badge_y = info_y + 15
    
    # Badge glow
    for i in range(5, 0, -1):
        alpha = 50 - i * 8
        draw.rounded_rectangle(
            [badge_x - i, badge_y - i, badge_x + badge_width + i, badge_y + badge_height + i],
            radius=21 + i,
            fill=(*status_color, alpha)
        )
    
    # Badge background with gradient
    badge_img = Image.new('RGBA', (badge_width, badge_height), (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge_img)
    for i in range(badge_height):
        ratio = i / badge_height
        alpha = int(60 * (1 - ratio * 0.3))
        badge_draw.rectangle([0, i, badge_width, i+1], fill=(*status_color, alpha))
    img.paste(badge_img, (badge_x, badge_y), badge_img)
    
    # Badge border
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
        radius=21,
        outline=status_color,
        width=3
    )
    
    # Badge text with shadow
    text_x = badge_x + (badge_width - len(status_text) * 12) // 2
    draw.text((text_x + 1, badge_y + 9), status_text, fill=(0, 0, 0, 150), font=fonts['medium'])
    draw.text((text_x, badge_y + 8), status_text, fill=status_color, font=fonts['medium'])
    
    # Generate premium QR code with frame
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
    
    qr_img = qr.make_image(fill_color=(10, 15, 35), back_color=(255, 255, 255))
    qr_img = qr_img.resize((150, 150), Image.Resampling.LANCZOS)
    
    # QR position - bottom right with premium frame
    qr_x = CARD_WIDTH - 350
    qr_y = CARD_HEIGHT - 290
    qr_size = 150
    
    # QR outer glow
    for i in range(8, 0, -1):
        alpha = 60 - i * 6
        draw.rounded_rectangle(
            [qr_x - 15 - i*2, qr_y - 15 - i*2, qr_x + qr_size + 15 + i*2, qr_y + qr_size + 15 + i*2],
            radius=18 + i*2,
            fill=(*COLOR_CYAN, alpha)
        )
    
    # Premium QR frame with gradient
    frame_padding = 12
    qr_frame = Image.new('RGBA', (qr_size + frame_padding*2, qr_size + frame_padding*2), (0, 0, 0, 0))
    qr_frame_draw = ImageDraw.Draw(qr_frame)
    
    # Frame gradient
    for i in range(qr_size + frame_padding*2):
        ratio = i / (qr_size + frame_padding*2)
        r = int(255 * (1 - ratio * 0.1))
        qr_frame_draw.rectangle([0, i, qr_size + frame_padding*2, i+1], fill=(r, r, r, 255))
    
    # Paste QR frame
    img.paste(qr_frame, (qr_x - frame_padding, qr_y - frame_padding), qr_frame)
    
    # Paste QR code
    img.paste(qr_img, (qr_x, qr_y))
    
    # Premium frame borders
    for i in range(3):
        offset = i * 2
        alpha = 255 - i * 60
        border_color = COLOR_GREEN if i % 2 == 0 else COLOR_CYAN
        draw.rounded_rectangle(
            [qr_x - frame_padding - offset, qr_y - frame_padding - offset, 
             qr_x + qr_size + frame_padding + offset, qr_y + qr_size + frame_padding + offset],
            radius=15 + offset,
            outline=(*border_color, alpha),
            width=2
        )
    
    # Corner accents for QR
    accent_len = 25
    accent_positions = [
        (qr_x - frame_padding - 6, qr_y - frame_padding - 6),  # Top-left
        (qr_x + qr_size + frame_padding - 19, qr_y - frame_padding - 6),  # Top-right
        (qr_x - frame_padding - 6, qr_y + qr_size + frame_padding - 19),  # Bottom-left
        (qr_x + qr_size + frame_padding - 19, qr_y + qr_size + frame_padding - 19)  # Bottom-right
    ]
    
    for pos in accent_positions:
        draw.rectangle([pos[0], pos[1], pos[0] + accent_len, pos[1] + 3], 
                      fill=(*TEXT_GOLD, 255))
        draw.rectangle([pos[0], pos[1], pos[0] + 3, pos[1] + accent_len], 
                      fill=(*TEXT_GOLD, 255))
    
    # QR label with glow
    label_text = "SCAN TO VERIFY"
    label_x = qr_x - frame_padding + 45
    label_y = qr_y + qr_size + frame_padding + 18
    draw.text((label_x + 1, label_y + 1), label_text, fill=(0, 0, 0, 120), font=fonts['micro'])
    draw.text((label_x, label_y), label_text, fill=TEXT_WHITE, font=fonts['micro'])
    
    # Validity information in premium card (bottom left)
    if member.created_at:
        valid_x = 50
        valid_y = CARD_HEIGHT - 150
        valid_width = 200
        valid_height = 100
        
        # Glass effect card
        create_glass_effect(draw, valid_x, valid_y, valid_width, valid_height, 15)
        
        # Content
        draw.text((valid_x + 15, valid_y + 15), "VALID FROM", fill=COLOR_CYAN, font=fonts['tiny'])
        valid_from = member.created_at.strftime('%B %Y')
        draw.text((valid_x + 16, valid_y + 36), valid_from, fill=(0, 0, 0, 120), font=fonts['small'])
        draw.text((valid_x + 15, valid_y + 35), valid_from, fill=TEXT_WHITE, font=fonts['small'])
        
        draw.text((valid_x + 15, valid_y + 62), "STATUS", fill=COLOR_CYAN, font=fonts['tiny'])
        draw.text((valid_x + 16, valid_y + 78), "ACTIVE", fill=(0, 0, 0, 120), font=fonts['tiny'])
        draw.text((valid_x + 15, valid_y + 77), "● ACTIVE", fill=COLOR_GREEN, font=fonts['tiny'])
    
    # Premium holographic bottom accent
    accent_height = 20
    holographic_accent = Image.new('RGBA', (CARD_WIDTH, accent_height), (0, 0, 0, 0))
    holo_draw = ImageDraw.Draw(holographic_accent)
    
    for x in range(CARD_WIDTH):
        # Create wave pattern
        ratio = (x / CARD_WIDTH) * 2 * math.pi
        wave = (math.sin(ratio * 3) + 1) / 2
        
        # Rainbow colors
        if x % 200 < 50:
            color = COLOR_GREEN
        elif x % 200 < 100:
            color = COLOR_CYAN
        elif x % 200 < 150:
            color = COLOR_BLUE_LIGHT
        else:
            color = COLOR_PURPLE
        
        alpha = int(80 * wave)
        holo_draw.line([(x, 0), (x, accent_height)], fill=(*color, alpha))
    
    img.paste(holographic_accent, (0, CARD_HEIGHT - accent_height), holographic_accent)
    
    # Apply holographic shine effect
    img = add_holographic_shine(img)
    
    # Convert back to RGB for saving
    if img.mode == 'RGBA':
        # Create white background
        bg = Image.new('RGB', img.size, (10, 15, 35))
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
    
    # Premium color scheme
    COLOR_BLUE = (25, 118, 210)
    COLOR_BLUE_LIGHT = (66, 165, 245)
    COLOR_GREEN = (46, 213, 115)
    COLOR_CYAN = (0, 184, 212)
    COLOR_PURPLE = (103, 58, 183)
    BG_DARK = (10, 15, 35)
    BG_DARKER = (5, 10, 25)
    TEXT_WHITE = (255, 255, 255)
    TEXT_LIGHT = (220, 230, 245)
    TEXT_GOLD = (255, 215, 0)
    
    # Create base with radial gradient
    img = draw_radial_gradient(CARD_WIDTH, CARD_HEIGHT, BG_DARK, BG_DARKER)
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Add diagonal gradient overlay for depth
    overlay = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for i in range(CARD_WIDTH + CARD_HEIGHT):
        ratio = i / (CARD_WIDTH + CARD_HEIGHT)
        alpha = int(40 * (1 - ratio))
        for x in range(max(0, i - CARD_HEIGHT), min(CARD_WIDTH, i)):
            y = i - x
            if 0 <= y < CARD_HEIGHT:
                overlay_draw.point((x, y), fill=(*COLOR_BLUE, alpha))
    img.paste(overlay, (0, 0), overlay)
    
    # Add premium geometric patterns
    add_premium_patterns(draw, CARD_WIDTH, CARD_HEIGHT)
    
    # Load fonts
    fonts = load_fonts()
    
    # Premium header with multi-color gradient
    header_height = 120
    header_gradient = Image.new('RGBA', (CARD_WIDTH, header_height), (0, 0, 0, 0))
    header_draw = ImageDraw.Draw(header_gradient)
    
    for i in range(header_height):
        ratio = i / header_height
        # Mix between purple and cyan
        r = int(COLOR_PURPLE[0] * (1 - ratio) + COLOR_CYAN[0] * ratio)
        g = int(COLOR_PURPLE[1] * (1 - ratio) + COLOR_CYAN[1] * ratio)
        b = int(COLOR_PURPLE[2] * (1 - ratio) + COLOR_CYAN[2] * ratio)
        alpha = int(120 * (1 - ratio * 0.7))
        header_draw.rectangle([0, i, CARD_WIDTH, i+1], fill=(r, g, b, alpha))
    
    img.paste(header_gradient, (0, 0), header_gradient)
    
    # Load and add logo at top center with glow
    logo_path = os.path.join(current_app.root_path, 'static', 'DigitalClub_LOGO copy.svg')
    logo = load_and_process_logo(logo_path, (100, 100))
    
    if logo:
        # Create glow effect
        glow = logo.copy()
        for _ in range(3):
            glow = glow.filter(ImageFilter.GaussianBlur(8))
        # Position logo at top center
        logo_x = CARD_WIDTH // 2 - 50
        img.paste(glow, (logo_x - 5, 15), glow)
        img.paste(logo, (logo_x, 20), logo)
    
    # Premium separator with gradient
    separator_y = 130
    sep_gradient = Image.new('RGBA', (CARD_WIDTH - 160, 3), (0, 0, 0, 0))
    sep_draw = ImageDraw.Draw(sep_gradient)
    for x in range(CARD_WIDTH - 160):
        ratio = x / (CARD_WIDTH - 160)
        alpha = int(255 * math.sin(ratio * math.pi))
        sep_draw.line([(x, 0), (x, 3)], fill=(*COLOR_GREEN, alpha))
    img.paste(sep_gradient, (80, separator_y), sep_gradient)
    
    # Premium content panels
    left_x = 60
    right_x = CARD_WIDTH // 2 + 30
    content_y = 160
    panel_width = (CARD_WIDTH // 2) - 90
    
    # Left panel - About section with glass effect
    left_panel_height = 180
    create_glass_effect(draw, left_x, content_y, panel_width, left_panel_height, 20)
    
    # About title with glow
    draw.text((left_x + 21, content_y + 16), "ABOUT THE CLUB", fill=(0, 0, 0, 120), font=fonts['medium'])
    draw.text((left_x + 20, content_y + 15), "ABOUT THE CLUB", fill=COLOR_GREEN, font=fonts['medium'])
    
    # About content
    about_text = [
        "The Digital Club is a vibrant",
        "community of tech enthusiasts,",
        "developers, and innovators at KIUT.",
        "",
        "We foster learning, collaboration,",
        "and innovation in technology."
    ]
    
    about_y = content_y + 50
    for line in about_text:
        if line:  # Skip empty lines for spacing
            draw.text((left_x + 21, about_y + 1), line, fill=(0, 0, 0, 80), font=fonts['tiny'])
            draw.text((left_x + 20, about_y), line, fill=TEXT_LIGHT, font=fonts['tiny'])
        about_y += 20
    
    # Contact panel
    contact_y = content_y + left_panel_height + 25
    contact_height = 140
    create_glass_effect(draw, left_x, contact_y, panel_width, contact_height, 20)
    
    # Contact title
    draw.text((left_x + 21, contact_y + 16), "CONTACT INFO", fill=(0, 0, 0, 120), font=fonts['medium'])
    draw.text((left_x + 20, contact_y + 15), "CONTACT INFO", fill=COLOR_CYAN, font=fonts['medium'])
    
    # Contact details with icons
    contact_info = [
        ("📧", "info@digitalclub.kiut.ac.tz"),
        ("🌐", "www.digitalclub.kiut.ac.tz"),
        ("📱", "+254 XXX XXX XXX")
    ]
    
    contact_text_y = contact_y + 50
    for icon, text in contact_info:
        draw.text((left_x + 20, contact_text_y), icon, font=fonts['small'])
        draw.text((left_x + 51, contact_text_y + 1), text, fill=(0, 0, 0, 80), font=fonts['tiny'])
        draw.text((left_x + 50, contact_text_y), text, fill=TEXT_LIGHT, font=fonts['tiny'])
        contact_text_y += 28
    
    # Right panel - Terms & Conditions with glass effect
    terms_panel_height = 180
    create_glass_effect(draw, right_x, content_y, panel_width, terms_panel_height, 20)
    
    # Terms title
    draw.text((right_x + 21, content_y + 16), "TERMS & CONDITIONS", fill=(0, 0, 0, 120), font=fonts['medium'])
    draw.text((right_x + 20, content_y + 15), "TERMS & CONDITIONS", fill=COLOR_PURPLE, font=fonts['medium'])
    
    # Terms list
    terms = [
        "• This card is non-transferable",
        "• Valid for current members only",
        "• Must be presented at events",
        "• Report if lost or stolen",
        "• Subject to club regulations",
        "• Expires upon graduation"
    ]
    
    terms_text_y = content_y + 50
    for term in terms:
        draw.text((right_x + 21, terms_text_y + 1), term, fill=(0, 0, 0, 80), font=fonts['tiny'])
        draw.text((right_x + 20, terms_text_y), term, fill=TEXT_LIGHT, font=fonts['tiny'])
        terms_text_y += 22
    
    # Security features panel (right bottom)
    security_y = content_y + terms_panel_height + 25
    security_height = 140
    create_glass_effect(draw, right_x, security_y, panel_width, security_height, 20)
    
    # Security title
    draw.text((right_x + 21, security_y + 16), "SECURITY FEATURES", fill=(0, 0, 0, 120), font=fonts['medium'])
    draw.text((right_x + 20, security_y + 15), "SECURITY FEATURES", fill=TEXT_GOLD, font=fonts['medium'])
    
    # Security features
    security_features = [
        "✓ Holographic elements",
        "✓ QR code verification",
        "✓ Unique member ID",
        "✓ Digital signature"
    ]
    
    security_text_y = security_y + 50
    for feature in security_features:
        draw.text((right_x + 21, security_text_y + 1), feature, fill=(0, 0, 0, 80), font=fonts['tiny'])
        draw.text((right_x + 20, security_text_y), feature, fill=TEXT_LIGHT, font=fonts['tiny'])
        security_text_y += 22
    
    # # Premium QR code for club website
    # if not base_url:
    #     try:
    #         base_url = request.url_root.rstrip('/')
    #     except:
    #         base_url = "https://digitalclub.kiut.ac.tz"
    
    # club_qr = qrcode.QRCode(
    #     version=1,
    #     error_correction=qrcode.constants.ERROR_CORRECT_H,
    #     box_size=8,
    #     border=2,
    # )
    # club_qr.add_data(base_url)
    # club_qr.make(fit=True)
    
    # qr_img = club_qr.make_image(fill_color=(10, 15, 35), back_color=(255, 255, 255))
    # qr_img = qr_img.resize((120, 120), Image.Resampling.LANCZOS)
    
    # # Position QR in center bottom area
    # qr_x = CARD_WIDTH // 2 - 60
    # qr_y = CARD_HEIGHT - 170
    # qr_size = 120
    
    # # QR outer glow
    # for i in range(6, 0, -1):
    #     alpha = 50 - i * 6
    #     draw.rounded_rectangle(
    #         [qr_x - 12 - i*2, qr_y - 12 - i*2, qr_x + qr_size + 12 + i*2, qr_y + qr_size + 12 + i*2],
    #         radius=15 + i*2,
    #         fill=(*COLOR_GREEN, alpha)
    #     )
    
    # # Premium QR frame
    # frame_padding = 10
    # qr_frame = Image.new('RGBA', (qr_size + frame_padding*2, qr_size + frame_padding*2), (255, 255, 255, 250))
    # img.paste(qr_frame, (qr_x - frame_padding, qr_y - frame_padding), qr_frame)
    # img.paste(qr_img, (qr_x, qr_y))
    
    # # Frame borders with multi-color
    # for i in range(3):
    #     offset = i * 2
    #     alpha = 255 - i * 60
    #     border_colors = [COLOR_GREEN, COLOR_CYAN, COLOR_BLUE_LIGHT]
    #     border_color = border_colors[i % 3]
    #     draw.rounded_rectangle(
    #         [qr_x - frame_padding - offset, qr_y - frame_padding - offset,
    #          qr_x + qr_size + frame_padding + offset, qr_y + qr_size + frame_padding + offset],
    #         radius=12 + offset,
    #         outline=(*border_color, alpha),
    #         width=2
    #     )
    
    # # QR label with style
    # label_text = "VISIT OUR WEBSITE"
    # label_x = qr_x - frame_padding + 10
    # label_y = qr_y + qr_size + frame_padding + 5
    # draw.text((label_x + 1, label_y + 1), label_text, fill=(0, 0, 0, 120), font=fonts['micro'])
    # draw.text((label_x, label_y), label_text, fill=COLOR_GREEN, font=fonts['micro'])
    
    # Signature line in premium style
    sig_y = CARD_HEIGHT - 130
    sig_line_start = 100
    sig_line_end = 380
    
    draw.text((sig_line_start, sig_y - 20), "AUTHORIZED SIGNATURE", fill=COLOR_CYAN, font=fonts['micro'])
    # Signature line with gradient
    for i in range(sig_line_end - sig_line_start):
        ratio = i / (sig_line_end - sig_line_start)
        alpha = int(255 * math.sin(ratio * math.pi))
        draw.line([(sig_line_start + i, sig_y), (sig_line_start + i + 1, sig_y)], 
                 fill=(*TEXT_LIGHT, alpha), width=2)
    
    # Premium magnetic strip effect
    strip_y = CARD_HEIGHT - 75
    strip_height = 60
    
    # Gradient magnetic strip
    strip_img = Image.new('RGBA', (CARD_WIDTH, strip_height), (0, 0, 0, 0))
    strip_draw = ImageDraw.Draw(strip_img)
    for i in range(strip_height):
        ratio = i / strip_height
        # Dark metallic gradient
        darkness = int(30 + 25 * math.sin(ratio * math.pi))
        alpha = 200
        strip_draw.rectangle([0, i, CARD_WIDTH, i+1], fill=(darkness, darkness, darkness + 5, alpha))
    
    # Add holographic lines to magnetic strip
    for x in range(0, CARD_WIDTH, 15):
        line_alpha = 40
        strip_draw.line([(x, 0), (x, strip_height)], fill=(100, 150, 200, line_alpha), width=1)
    
    img.paste(strip_img, (0, strip_y), strip_img)
    
    # Footer with copyright
    footer_y = CARD_HEIGHT - 95
    footer_text = f"© {member.created_at.year if member.created_at else '2024'} KIUT DIGITAL CLUB  •  ALL RIGHTS RESERVED"
    footer_x = CARD_WIDTH // 2 - len(footer_text) * 3
    draw.text((footer_x + 1, footer_y + 1), footer_text, fill=(0, 0, 0, 150), font=fonts['micro'])
    draw.text((footer_x, footer_y), footer_text, fill=TEXT_LIGHT, font=fonts['micro'])
    
    # Premium corner accents
    corner_size = 80
    # Top right
    for i in range(3):
        offset = i * 15
        alpha = 80 - i * 20
        points = [
            (CARD_WIDTH - corner_size + offset, 0),
            (CARD_WIDTH, 0),
            (CARD_WIDTH, corner_size - offset)
        ]
        draw.polygon(points, fill=(*COLOR_PURPLE, alpha))
    
    # Bottom left
    for i in range(3):
        offset = i * 15
        alpha = 80 - i * 20
        points = [
            (0, CARD_HEIGHT - corner_size + offset),
            (0, CARD_HEIGHT),
            (corner_size - offset, CARD_HEIGHT)
        ]
        draw.polygon(points, fill=(*COLOR_CYAN, alpha))
    
    # Apply holographic shine
    img = add_holographic_shine(img)
    
    # Convert back to RGB
    if img.mode == 'RGBA':
        bg = Image.new('RGB', img.size, (10, 15, 35))
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

