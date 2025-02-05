from PIL import Image, ImageDraw

def create_placeholder_icons():
    # Create base image (1024x1024 for maximum compatibility)
    size = 1024
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a simple circle
    margin = size // 4
    draw.ellipse([margin, margin, size - margin, size - margin], 
                 fill='#2196F3')  # Material Blue
    
    # Save PNG
    img.save('resources/icons/icon.png')
    
    # Save ICO for Windows
    img.resize((256, 256)).save('resources/icons/icon.ico')
    
    # Save high-res PNG for macOS
    img.save('resources/icons/icon_1024.png')

if __name__ == "__main__":
    create_placeholder_icons() 