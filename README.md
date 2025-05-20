# Video to Pixel Spritesheet

This project provides a Python script (`vid-to-pixel-spritesheet.py`) that automates the process of converting a video file (`target.mp4`) into a pixel art spritesheet and an animated GIF.

## Pipeline Steps

1.  **Video Decompilation**: Extracts frames from the input video using `ffmpeg`.
2.  **Background Removal**: Removes the background from each frame using `rembg`.
3.  **Pixelation**: Resizes the background-removed frames to a smaller dimension to achieve a pixelated effect using Pillow.
4.  **Color Quantization**: Reduces the color palette of the pixelated frames using Pillow.
5.  **Spritesheet Creation**: Stitches the final processed frames into a horizontal spritesheet (PNG).
6.  **GIF Creation**: Creates an animated GIF from the final processed frames using `ffmpeg`.

## Prerequisites

*   Python 3
*   ffmpeg: Must be installed and accessible in your system's PATH.
*   Python libraries:
    *   Pillow
    *   rembg
    *   numpy (<2.0, as `rembg`'s dependency `onnxruntime` may require it)

Install Python dependencies using pip:
```bash
pip install Pillow rembg "numpy<2"
```

## Usage

1.  Place your input video named `target.mp4` in the same directory as the script.
2.  Run the script:
    ```bash
    python vid-to-pixel-spritesheet.py
    ```
3.  Outputs will be saved in a directory named `test_pipeline_output`. This includes:
    *   Intermediate frames from each processing stage.
    *   `final_spritesheet.png`
    *   `final_animation.gif`

## Configuration

The script contains configuration variables at the top that can be adjusted:
*   `INPUT_VIDEO`: Path to the input video file.
*   `BASE_OUTPUT_DIR`: Name of the main output directory.
*   Directory names for intermediate frames.
*   `SPRITESHEET_OUTPUT_FILE`, `GIF_OUTPUT_FILE`.
*   `VIDEO_FPS`, `GIF_FPS`, `GIF_FRAME_SKIP_RATIO`.
*   `PIXELATION_DOWNSCALE_FACTOR`: Factor for resizing images.
*   `QUANTIZE_COLORS`: Number of colors for quantization. 