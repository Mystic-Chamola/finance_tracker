from PIL import Image, ImageDraw, ImageFont
import os

# Create icons directory
os.makedirs('static/icons', exist_ok=True)

def create_icon(size, filename):
    # Create a blue gradient background
    img = Image.new('RGB', (size, size), color=(37, 99, 235))  # #2563eb
    draw = ImageDraw.Draw(img)
    
    # Draw a white money bag emoji (using text)
    try:
        # Try to use a system font that supports emoji
        font = ImageFont.truetype('/System/Library/Fonts/Apple Color Emoji.ttc', size=int(size * 0.5))
    except:
        # Fallback to default
        font = ImageFont.load_default()
    
    # Draw 💰 in the center
    text = "💰"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((size - text_width) // 2, (size - text_height) // 2)
    draw.text(position, text, fill='white', font=font)
    
    img.save(f'static/icons/{filename}')
    print(f'Created {filename}')

# Generate both sizes
create_icon(192, 'icon-192.png')
create_icon(512, 'icon-512.png')