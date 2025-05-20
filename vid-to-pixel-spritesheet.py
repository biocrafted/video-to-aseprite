import os
import subprocess
import shutil
from PIL import Image
from rembg import remove, new_session # Modified import
import math # Added for GIF creation

# --- CONFIGURATION ---
INPUT_VIDEO = "target.mp4"
BASE_OUTPUT_DIR = "test_pipeline_output" # Renamed to avoid confusion with other test outputs
RAW_FRAMES_DIR = os.path.join(BASE_OUTPUT_DIR, "01_raw_frames")
NO_BG_FRAMES_DIR = os.path.join(BASE_OUTPUT_DIR, "02_no_bg_frames")
PIXELATED_FRAMES_DIR = os.path.join(BASE_OUTPUT_DIR, "03_pixelated_frames")
FINAL_FRAMES_DIR = os.path.join(BASE_OUTPUT_DIR, "04_final_frames")
SPRITESHEET_OUTPUT_FILE = os.path.join(BASE_OUTPUT_DIR, "final_spritesheet.png")

# GIF Configuration
GIF_OUTPUT_FILE = os.path.join(BASE_OUTPUT_DIR, "final_animation.gif")
GIF_FPS = 10  # Frames per second for the output GIF
GIF_FRAME_SKIP_RATIO = 1 # Use 1 for no skip. 2 for every 2nd frame, etc.
GIF_FRAME_PATTERN = "frame_%04d.png" # Expected pattern in the final frames folder

VIDEO_FPS = 25 # FPS for extracting frames
PIXELATION_DOWNSCALE_FACTOR = 8 # Factor by which to downscale the image dimensions (e.g., 8 means 1/8th size)
QUANTIZE_COLORS = 16 # Number of colors for final quantization


# --- HELPER FUNCTIONS ---

def check_ffmpeg():
    """Checks if ffmpeg is installed and in the system PATH."""
    if shutil.which("ffmpeg") is None:
        print("ERROR: ffmpeg not found. Please install ffmpeg and ensure it is in your PATH.")
        print("You can download it from https://ffmpeg.org/download.html")
        print("On macOS with Homebrew, you can install it with: brew install ffmpeg")
        print("On Debian/Ubuntu, you can install it with: sudo apt update && sudo apt install ffmpeg")
        return False
    print("ffmpeg found.")
    return True

def create_directories():
    """Creates all necessary output directories."""
    dirs_to_create = [
        BASE_OUTPUT_DIR,
        RAW_FRAMES_DIR,
        NO_BG_FRAMES_DIR,
        PIXELATED_FRAMES_DIR,
        FINAL_FRAMES_DIR
    ]
    for dir_path in dirs_to_create:
        if os.path.exists(dir_path):
            print(f"Directory {dir_path} already exists. Clearing it.")
            shutil.rmtree(dir_path)
        os.makedirs(dir_path)
        print(f"Created directory: {dir_path}")

def decompile_video(video_path, output_dir, fps):
    """Decompiles a video into frames using ffmpeg."""
    print(f"Decompiling video '{video_path}' into '{output_dir}' at {fps} FPS...")
    if not os.path.exists(video_path):
        print(f"ERROR: Input video not found at {video_path}")
        return False

    # Ensure output directory for frames exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created subdirectory for frames: {output_dir}")

    output_pattern = os.path.join(output_dir, "frame_%04d.png")
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps={fps}",
        output_pattern
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Video decompiled successfully. Frames are in {output_dir}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during video decompilation: {e}")
        print(f"ffmpeg stdout: {e.stdout}")
        print(f"ffmpeg stderr: {e.stderr}")
        return False

def process_frames_pixelate(input_dir, output_dir, downscale_factor):
    """Pixelates frames by resizing down to a fraction of original size."""
    print(
        f"Pixelating frames in '{input_dir}' using downscale factor 1/{downscale_factor}, output to '{output_dir}'...")

    if not os.path.exists(input_dir):
        print(f"ERROR: Input directory for pixelation not found: {input_dir}")
        return False
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in sorted(os.listdir(input_dir)):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            try:
                print(f"  Processing (pixelate): {filename}")
                img = Image.open(input_path)
                original_width, original_height = img.size

                if downscale_factor <= 0:
                    print("  Warning: PIXELATION_DOWNSCALE_FACTOR must be > 0. Skipping pixelation for this file.")
                    shutil.copy(input_path, output_path)
                    continue
                
                final_width = original_width // downscale_factor
                final_height = original_height // downscale_factor

                # Ensure dimensions are at least 1x1
                if final_width == 0: 
                    final_width = 1
                    print(f"  Warning: Calculated pixelated width was 0 for {filename}. Clamped to 1.")
                if final_height == 0: 
                    final_height = 1
                    print(f"  Warning: Calculated pixelated height was 0 for {filename}. Clamped to 1.")

                # Resize directly to the final pixelated size.
                # Image.Resampling.BOX is often good for a blocky/mosaic downscale.
                # Image.Resampling.NEAREST is an alternative for a sharper, sampled look.
                pixelated_img = img.resize(
                    (final_width, final_height), Image.Resampling.BOX)

                pixelated_img.save(output_path)
            except Exception as e:
                print(f"    Error pixelating {filename}: {e}")
    print("Pixelation stage complete.")
    return True

def process_frames_remove_background(input_dir, output_dir):
    """Removes background from frames using a reusable rembg session."""
    print(f"Processing frames in '{input_dir}' to remove background, output to '{output_dir}'...")
    
    if not os.path.exists(input_dir):
        print(f"ERROR: Input directory for background removal not found: {input_dir}")
        return False
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Create a rembg session to reuse the model
    try:
        print("  Initializing rembg session (model will be loaded once)...")
        session = new_session() # Uses default model, e.g., u2net
        print("  rembg session initialized.")
    except Exception as e:
        print(f"    Error initializing rembg session: {e}")
        print(f"    Make sure you have a model downloaded (e.g., by running rembg once from CLI or ensuring model files are in ~/.u2net)")
        return False

    for filename in sorted(os.listdir(input_dir)):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            try:
                print(f"  Processing (bg remove): {filename}")
                with open(input_path, 'rb') as i:
                    with open(output_path, 'wb') as o:
                        input_data = i.read()
                        # Use the session for background removal - reverting to default (no explicit alpha matting)
                        output_data = remove(input_data, 
                                             session=session)
                        o.write(output_data)
            except Exception as e:
                print(f"    Error removing background from {filename}: {e}")
    print("Background removal stage complete.")
    return True

def process_frames_quantize(input_dir, output_dir, num_colors):
    """Quantizes colors of frames."""
    print(f"Quantizing frames in '{input_dir}' to {num_colors} colors, output to '{output_dir}'...")

    if not os.path.exists(input_dir):
        print(f"ERROR: Input directory for quantization not found: {input_dir}")
        return False
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in sorted(os.listdir(input_dir)):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            try:
                print(f"  Processing (quantize): {filename}")
                img = Image.open(input_path)
                # Ensure image is in a mode that quantize can handle well, like RGBA or RGB
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGBA')
                
                # Use FASTOCTREE for RGBA images, as MAXCOVERAGE doesn't support it well for alpha.
                # LIBIMAGEQUANT (method=3) is another option if quality with FASTOCTREE is not sufficient,
                # but requires libimagequant library to be installed.
                quantized_img = img.quantize(colors=num_colors, method=Image.Quantize.FASTOCTREE)
                
                # Ensure the final output is RGBA to preserve transparency
                quantized_img = quantized_img.convert('RGBA')

                quantized_img.save(output_path)
            except Exception as e:
                print(f"    Error quantizing {filename}: {e}")
    print("Quantization stage complete.")
    return True

def create_gif_from_frames(input_dir, frame_pattern_name, output_gif_path, base_output_dir, input_framerate, gif_fps, frame_skip_ratio):
    """Creates a GIF from the image frames in input_dir using ffmpeg."""
    print(f"Creating GIF from frames in '{input_dir}', saving to '{output_gif_path}'...")

    frame_files = sorted([f for f in os.listdir(input_dir) if f.lower().startswith("frame_") and f.lower().endswith(".png")])
    num_available_physical_frames = len(frame_files)

    if num_available_physical_frames == 0:
        print(f"No frames found in {input_dir} matching pattern for GIF creation.")
        return False

    # Assuming frames start from 1 as per ffmpeg's default decompilation pattern
    start_frame_number = 1 
    # If your frames could start from 0, you'd need to detect that, e.g. by parsing frame_files[0]

    actual_frame_skip_ratio = max(1, frame_skip_ratio)

    encoded_frames_count = math.ceil(num_available_physical_frames / actual_frame_skip_ratio)
    if encoded_frames_count == 0 and num_available_physical_frames > 0:
        encoded_frames_count = 1

    palette_path = os.path.join(base_output_dir, "palette.png")
    full_frame_pattern_path = os.path.join(input_dir, frame_pattern_name)

    # Palette generation (pass 1)
    # No scaling here, frames are assumed to be final size
    palette_cmd = [
        "ffmpeg",
        "-v", "warning",
        "-framerate", str(input_framerate),
        "-start_number", str(start_frame_number),
        "-i", full_frame_pattern_path,
        "-vf", f"select='not(mod(n,{actual_frame_skip_ratio}))',setpts=N/{gif_fps}/TB,fps={gif_fps},palettegen",
        "-frames:v", str(int(encoded_frames_count)),
        "-y", palette_path
    ]
    print(f"  Generating palette for GIF: {' '.join(palette_cmd)}")
    try:
        subprocess.run(palette_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"    Error generating palette: {e}")
        print(f"    ffmpeg stdout: {e.stdout}")
        print(f"    ffmpeg stderr: {e.stderr}")
        if os.path.exists(palette_path):
            os.remove(palette_path)
        return False

    # GIF creation using the palette (pass 2)
    # No scaling here
    gif_cmd = [
        "ffmpeg",
        "-v", "warning",
        "-framerate", str(input_framerate),
        "-start_number", str(start_frame_number),
        "-i", full_frame_pattern_path,
        "-i", palette_path,
        "-lavfi", f"[0:v]select='not(mod(n,{actual_frame_skip_ratio}))',setpts=N/{gif_fps}/TB,fps={gif_fps}[processed_frames];[processed_frames][1:v]paletteuse",
        "-loop", "0", # 0 for infinite loop
        "-frames:v", str(int(encoded_frames_count)),
        "-y", output_gif_path
    ]
    print(f"  Creating GIF: {' '.join(gif_cmd)}")
    try:
        subprocess.run(gif_cmd, check=True, capture_output=True, text=True)
        print(f"Successfully created GIF: {output_gif_path}")
    except subprocess.CalledProcessError as e:
        print(f"    Error creating GIF: {e}")
        print(f"    ffmpeg stdout: {e.stdout}")
        print(f"    ffmpeg stderr: {e.stderr}")
        return False
    finally:
        if os.path.exists(palette_path):
            os.remove(palette_path)
            print(f"  Cleaned up {palette_path}")
    return True

def create_spritesheet(input_dir, output_file):
    """Creates a spritesheet from frames in the input directory."""
    print(f"Creating spritesheet from frames in '{input_dir}', saving to '{output_file}'...")
    
    frames = []
    filenames = sorted([f for f in os.listdir(input_dir) if f.lower().endswith(".png")]) # Assuming PNGs

    if not filenames:
        print(f"Error: No frames found in {input_dir} to create spritesheet.")
        return False

    for filename in filenames:
        try:
            img_path = os.path.join(input_dir, filename)
            img = Image.open(img_path)
            # Ensure all frames are RGBA for consistent pasting with transparency
            frames.append(img.convert("RGBA"))
        except Exception as e:
            print(f"    Error loading frame {filename} for spritesheet: {e}")
            return False
    
    if not frames:
        print("Error: Frame list is empty after loading attempts.")
        return False

    max_height = 0
    total_width = 0
    for frame in frames:
        if frame.height > max_height:
            max_height = frame.height
        total_width += frame.width
    
    print(f"  Spritesheet dimensions: {total_width}w x {max_height}h, from {len(frames)} frames.")

    spritesheet = Image.new('RGBA', (total_width, max_height), (0, 0, 0, 0)) # Transparent background

    current_x = 0
    for frame in frames:
        spritesheet.paste(frame, (current_x, 0))
        current_x += frame.width
    
    try:
        spritesheet.save(output_file)
        print(f"Spritesheet saved successfully to {output_file}")
        return True
    except Exception as e:
        print(f"Error saving spritesheet {output_file}: {e}")
        return False

# --- MAIN EXECUTION ---
def main():
    print("Starting video to pixel spritesheet pipeline...")

    if not check_ffmpeg():
        return

    create_directories()

    # Stage 1: Decompile video
    if not decompile_video(INPUT_VIDEO, RAW_FRAMES_DIR, VIDEO_FPS):
        print("Halting pipeline due to video decompilation error.")
        return

    # Stage 2: Remove background (on full-resolution frames)
    if not process_frames_remove_background(RAW_FRAMES_DIR, NO_BG_FRAMES_DIR):
        print("Halting pipeline due to background removal error.")
        return

    # Stage 3: Pixelate frames (now on background-removed frames)
    if not process_frames_pixelate(NO_BG_FRAMES_DIR, PIXELATED_FRAMES_DIR, PIXELATION_DOWNSCALE_FACTOR):
        print("Halting pipeline due to pixelation error.")
        return

    # Stage 4: Quantize colors
    if not process_frames_quantize(PIXELATED_FRAMES_DIR, FINAL_FRAMES_DIR, QUANTIZE_COLORS):
        print("Halting pipeline due to quantization error.")
        return

    # Stage 5: Create spritesheet
    if not create_spritesheet(FINAL_FRAMES_DIR, SPRITESHEET_OUTPUT_FILE):
        print("Halting pipeline due to spritesheet creation error.")
        return

    # Stage 6: Create GIF
    if not create_gif_from_frames(FINAL_FRAMES_DIR, GIF_FRAME_PATTERN, GIF_OUTPUT_FILE, 
                                  BASE_OUTPUT_DIR, VIDEO_FPS, GIF_FPS, GIF_FRAME_SKIP_RATIO):
        print("Pipeline warning: GIF creation failed.") # Non-fatal, spritesheet might still be fine
        # return # Uncomment if GIF is critical

    print(f"\nPipeline complete!")
    print(f"  Output spritesheet: {SPRITESHEET_OUTPUT_FILE}")
    print(f"  Output GIF: {GIF_OUTPUT_FILE}")
    print(f"Intermediate files are in subdirectories within: {BASE_OUTPUT_DIR}")

if __name__ == "__main__":
    main()
