import os
import subprocess
import shutil
from PIL import Image
from rembg import remove, new_session # Restored for default background removal
from transparent_background import Remover # For high-quality background removal
import math # Added for GIF creation
import argparse # For command-line arguments

# --- CONFIGURATION ---
INPUT_VIDEO = "target.mp4"
BASE_OUTPUT_DIR = "test_pipeline_output" # Main output directory
RAW_FRAMES_DIR = os.path.join(BASE_OUTPUT_DIR, "01_raw_frames")
NO_BG_FRAMES_DIR = os.path.join(BASE_OUTPUT_DIR, "02_no_bg_frames") # Output of RemBG
PIXELATED_FRAMES_DIR = os.path.join(BASE_OUTPUT_DIR, "03_pixelated_frames") # Output of Pixelate
# QUANTIZED_FRAMES_DIR no longer needed for this pipeline order
FINAL_FRAMES_DIR = os.path.join(BASE_OUTPUT_DIR, "04_final_frames") # Output of Quantize
SPRITESHEET_OUTPUT_FILE = os.path.join(BASE_OUTPUT_DIR, "final_spritesheet.png")

# GIF Configuration
GIF_OUTPUT_FILE = os.path.join(BASE_OUTPUT_DIR, "final_animation.gif")
GIF_FPS = 10  # Frames per second for the output GIF
GIF_FRAME_SKIP_RATIO = 1 # Use 1 for no skip. 2 for every 2nd frame, etc.
GIF_FRAME_PATTERN = "frame_%04d.png" # Expected pattern in the final frames folder

VIDEO_FPS = 25 # FPS for extracting frames
PIXELATION_DOWNSCALE_FACTOR = 8 # Factor by which to downscale the image dimensions (e.g., 8 means 1/8th size)
QUANTIZE_COLORS = 32 # Number of colors for final quantization
MAX_PALETTE_FRAMES = 50 # Max frames to sample for global palette generation


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
        NO_BG_FRAMES_DIR,     # For 1st BG removal output
        PIXELATED_FRAMES_DIR, # For pixelation output
        FINAL_FRAMES_DIR      # For quantization output
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

def process_frames_remove_background(input_dir, output_dir, use_high_quality_model: bool):
    """Removes background from frames.
    Uses rembg by default, or InSPyReNet if use_high_quality_model is True.
    """
    
    if not os.path.exists(input_dir):
        print(f"ERROR: Input directory for background removal not found: {input_dir}")
        return False
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if use_high_quality_model:
        print(f"Processing frames in '{input_dir}' to remove background (using InSPyReNet - High Quality), output to '{output_dir}'...")
        try:
            print("  Initializing InSPyReNet model (will be loaded once)...")
            remover = Remover() # Using default settings for InSPyReNet
            print("  InSPyReNet model initialized.")
        except Exception as e:
            print(f"    Error initializing InSPyReNet Remover: {e}")
            return False

        for filename in sorted(os.listdir(input_dir)):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                input_path = os.path.join(input_dir, filename)
                output_path = os.path.join(output_dir, filename) 
                try:
                    print(f"  Processing (bg remove with InSPyReNet): {filename}")
                    img = Image.open(input_path).convert('RGB') 
                    out_img = remover.process(img)
                    out_img.save(output_path, "PNG")
                except Exception as e:
                    print(f"    Error removing background from {filename} using InSPyReNet: {e}")
        print("Background removal stage with InSPyReNet complete.")
    else:
        print(f"Processing frames in '{input_dir}' to remove background (using rembg - Default Quality), output to '{output_dir}'...")
        try:
            print("  Initializing rembg session (model u2net will be loaded once)...")
            # Using default u2net model for rembg
            session = new_session(model_name="u2net") 
            print("  rembg session initialized with model: u2net")
        except Exception as e:
            print(f"    Error initializing rembg session: {e}")
            return False

        for filename in sorted(os.listdir(input_dir)):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                input_path = os.path.join(input_dir, filename)
                output_path = os.path.join(output_dir, filename)
                try:
                    print(f"  Processing (bg remove with rembg): {filename}")
                    with open(input_path, 'rb') as i:
                        with open(output_path, 'wb') as o:
                            input_data = i.read()
                            output_data = remove(input_data, session=session)
                            o.write(output_data)
                except Exception as e:
                    print(f"    Error removing background from {filename} using rembg: {e}")
        print("Background removal stage with rembg complete.")
    return True

def process_frames_quantize(input_dir, output_dir, num_colors, global_palette_image=None):
    """Quantizes colors of frames, preserving original alpha, optionally using a global palette."""
    operation_type = "using global palette" if global_palette_image else "generating individual palettes"
    print(f"Quantizing frames in '{input_dir}' to {num_colors} colors ({operation_type}, MEDIANCUT, preserving original alpha), output to '{output_dir}'...")

    if not os.path.exists(input_dir):
        print(f"ERROR: Input directory for quantization not found: {input_dir}")
        return False
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in sorted(os.listdir(input_dir)):
        if filename.lower().endswith((".png")): # Expecting PNGs with alpha from pixelation
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            try:
                print(f"  Processing (quantize {operation_type}): {filename}")
                img = Image.open(input_path)

                if img.mode != 'RGBA':
                    print(f"  Warning: Frame {filename} for quantization is not RGBA, converting. This is unexpected if preceeded by background removal.")
                    img = img.convert('RGBA')

                # Separate original alpha channel
                original_alpha_channel = img.split()[-1]
                
                # Convert to RGB for quantization (original alpha is kept aside)
                rgb_img = img.convert('RGB')

                # Quantize the RGB image
                if global_palette_image:
                    quantized_p_img = rgb_img.quantize(
                        palette=global_palette_image,
                        dither=Image.Dither.NONE
                    )
                else:
                    print(f"  Warning: No global palette provided for {filename}. Generating individual palette.")
                    quantized_p_img = rgb_img.quantize(
                        colors=num_colors, 
                        method=Image.Quantize.MEDIANCUT,
                        dither=Image.Dither.NONE
                    )
                
                # Convert palettized image back to RGB
                final_rgb_img = quantized_p_img.convert("RGB")

                # Merge the quantized RGB data with the original alpha channel
                final_output_img = Image.merge("RGBA", final_rgb_img.split() + (original_alpha_channel,))
                
                final_output_img.save(output_path)

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

def generate_global_palette(frame_source_dir, num_colors, max_frames_to_sample):
    """Generates a global palette from a sample of frames."""
    print(f"Generating global palette from up to {max_frames_to_sample} frames in {frame_source_dir}...")
    source_frames = []
    for filename in sorted(os.listdir(frame_source_dir)):
        if filename.lower().endswith((".png")):
            source_frames.append(os.path.join(frame_source_dir, filename))
    
    if not source_frames:
        print("  No source frames found to generate global palette. Will use individual palettes.")
        return None

    # Sample frames for palette generation
    sample_frames_paths = source_frames[:max_frames_to_sample]
    
    loaded_images = []
    total_width = 0
    max_height = 0

    for frame_path in sample_frames_paths:
        try:
            img = Image.open(frame_path)
            if img.mode != 'RGBA': # Ensure RGBA for consistent processing before palette generation
                img = img.convert('RGBA')
            
            # For palette generation, we need to feed the quantizer opaque colors.
            # Composite onto white, then convert to RGB.
            white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            composited_for_palette = Image.alpha_composite(white_bg, img)
            rgb_for_palette = composited_for_palette.convert("RGB")
            loaded_images.append(rgb_for_palette)
            
            total_width += rgb_for_palette.width
            if rgb_for_palette.height > max_height:
                max_height = rgb_for_palette.height
        except Exception as e:
            print(f"  Warning: Could not load or process frame {frame_path} for palette generation: {e}")

    if not loaded_images:
        print("  No images successfully loaded for global palette. Will use individual palettes.")
        return None

    # Create a contact sheet of the sampled (and processed for palette) images
    # This gives the quantizer a good overview of all colors
    contact_sheet = Image.new('RGB', (total_width, max_height))
    current_x = 0
    for img in loaded_images:
        contact_sheet.paste(img, (current_x, 0))
        current_x += img.width
    
    print(f"  Generating palette from contact sheet ({len(loaded_images)} frames, {contact_sheet.width}x{contact_sheet.height})...")
    try:
        # Quantize the contact sheet to get the global palette
        # The result is a 'P' mode image, which itself serves as the palette
        global_palette = contact_sheet.quantize(
            colors=num_colors,
            method=Image.Quantize.MEDIANCUT # Consistent with per-frame quantization
        )
        print("  Global palette generated successfully.")
        return global_palette
    except Exception as e:
        print(f"  Error generating global palette: {e}. Will fall back to individual palettes.")
        return None

# --- MAIN EXECUTION ---
def main():
    parser = argparse.ArgumentParser(description="Convert a video to a pixel art spritesheet and GIF.")
    parser.add_argument(
        "--high-quality",
        action="store_true",
        help="Use InSPyReNet for background removal (slower, potentially higher quality) instead of rembg."
    )
    args = parser.parse_args()

    print("Starting video to pixel spritesheet pipeline...")
    if args.high_quality:
        print("High-quality background removal mode enabled (using InSPyReNet).")
    else:
        print("Default background removal mode enabled (using rembg).")


    if not check_ffmpeg():
        return

    create_directories()

    # Stage 1: Decompile video
    if not decompile_video(INPUT_VIDEO, RAW_FRAMES_DIR, VIDEO_FPS):
        print("Halting pipeline due to video decompilation error.")
        return

    # Stage 2: Remove Background (Pass 1)
    if not process_frames_remove_background(RAW_FRAMES_DIR, NO_BG_FRAMES_DIR, args.high_quality):
        print("Halting pipeline due to background removal error.")
        return

    # Stage 3: Pixelate Frames (on background-removed frames)
    if not process_frames_pixelate(NO_BG_FRAMES_DIR, PIXELATED_FRAMES_DIR, PIXELATION_DOWNSCALE_FACTOR):
        print("Halting pipeline due to pixelation error.")
        return

    # Stage 4: Generate Global Palette (from pixelated, background-removed frames)
    global_palette_img = generate_global_palette(PIXELATED_FRAMES_DIR, QUANTIZE_COLORS, MAX_PALETTE_FRAMES)

    # Stage 5: Quantize Colors (on pixelated, background-removed frames)
    # Output directly to FINAL_FRAMES_DIR
    if not process_frames_quantize(PIXELATED_FRAMES_DIR, FINAL_FRAMES_DIR, QUANTIZE_COLORS, global_palette_image=global_palette_img):
        print("Halting pipeline due to quantization error.")
        return

    # Stage 6: Create spritesheet (from final processed frames)
    if not create_spritesheet(FINAL_FRAMES_DIR, SPRITESHEET_OUTPUT_FILE):
        print("Halting pipeline due to spritesheet creation error.")
        return

    # Stage 7: Create GIF (from final processed frames)
    if not create_gif_from_frames(FINAL_FRAMES_DIR, GIF_FRAME_PATTERN, GIF_OUTPUT_FILE, 
                                  BASE_OUTPUT_DIR, VIDEO_FPS, GIF_FPS, GIF_FRAME_SKIP_RATIO):
        print("Pipeline warning: GIF creation failed.") # Non-fatal

    print(f"\nPipeline complete!")
    print(f"  Output spritesheet: {SPRITESHEET_OUTPUT_FILE}")
    print(f"  Output GIF: {GIF_OUTPUT_FILE}")
    print(f"Intermediate files are in subdirectories within: {BASE_OUTPUT_DIR}")

if __name__ == "__main__":
    main()
