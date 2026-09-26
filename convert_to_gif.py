import os
from PIL import Image

frames_dir = "/tmp/gif_frames"
output_gif = "/config/Desktop/Session1/smart-pantry-concierge/demo.gif"

files = sorted([f for f in os.listdir(frames_dir) if f.endswith(".png")])
print(f"Total frames found: {len(files)}")

# Subsample frames if needed for size optimization (e.g. every 2nd frame for crisp 6fps smooth playback)
images = []
for idx, filename in enumerate(files):
    if idx % 1 == 0:  # Include frames
        filepath = os.path.join(frames_dir, filename)
        img = Image.open(filepath)
        # Convert to P mode with palette for optimized file size
        images.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))

if images:
    # Save as looping GIF (duration=150ms per frame = ~6.6 fps)
    images[0].save(
        output_gif,
        save_all=True,
        append_images=images[1:],
        optimize=True,
        duration=150,
        loop=0
    )
    size_mb = os.path.getsize(output_gif) / (1024 * 1024)
    print(f"Looping GIF created successfully at {output_gif} ({size_mb:.2f} MB)")
