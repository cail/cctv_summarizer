# CCTV Summarizer

A Python tool for capturing frames from RTSP cameras and generating time-lapse summary videos. Ideal for monitoring multiple cameras with activity-focused recording using motion detection.

**IMPORTANT NOTE** Majority of this project was created by Copilot, using my instructions.

## Features

- **Multi-camera support**: Monitor multiple RTSP cameras simultaneously
- **Motion detection**: Optional motion tracking to capture only frames with activity
- **Automatic cleanup**: Removes old frames based on configurable retention period (default: 24 hours)
- **Video generation**: Creates time-lapse videos from captured frames (default: hourly)
- **Efficient storage**: Organizes frames and videos in separate directories per camera
- **Configurable**: Easy YAML-based configuration

## Requirements

- Python 3.7+
- ffmpeg (for frame capture and video generation)
- OpenCV (for motion detection)

## Installation

1. **Install system dependencies**:
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   ```

2. **Install Python dependencies**:
   ```bash
   cd /Users/igor/Projects/HomeAssistaint/scripts/ha-config/cctv_summarizer
   pip3 install -r requirements.txt
   ```

   Or use a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Configuration

Edit `config.yaml` to configure your cameras and settings:

```yaml
config:
    summary_duration: 24h      # How long to keep captured frames
    capture_interval: 1m       # How often to capture frames
    video_generation_interval: 1h  # How often to generate videos (optional, defaults to 1h)
    output_path: ../www/cctv_summaries/  # Where to store frames and videos
    video_format: mp4          # Output video format
    resolution: 720p           # Output video resolution

cameras:
    front:
        name: Front Door Camera
        track_changes: true    # Enable motion detection (only save frames with activity)
        url: rtsp://user:pass@192.168.1.15:554/stream
    
    park:
        name: Parking Lot
        url: rtsp://user:pass@192.168.1.16:554/stream
```

### Configuration Options

- **summary_duration**: How long to retain captured frames (e.g., `24h`, `2d`, `168h`)
- **capture_interval**: Time between frame captures (e.g., `30s`, `1m`, `5m`)
- **video_generation_interval**: Time between video generations (e.g., `1h`, `6h`, `24h`)
- **output_path**: Directory for storing frames and videos
- **video_format**: Video output format (`mp4`, `avi`, etc.)
- **resolution**: Video height in pixels (e.g., `720p`, `1080p`)
- **video_fps**: Frames per second for generated videos (default: `25`) - each captured image becomes one frame
- **log_level**: Logging verbosity - `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` (default: `INFO`)
- **track_changes**: Enable motion detection for a camera (applies filtering during video generation - all frames are still captured)

### Motion Detection Parameters

Motion detection filters frames **during video generation**, not during capture. All frames are saved, but only frames with detected motion are included in the generated videos. This allows you to tune parameters without losing data.

```yaml
config:
    # Global defaults
    motion_threshold: 25      # Pixel difference threshold (0-255, higher = less sensitive)
    min_motion_area: 500      # Minimum contour area in pixels (higher = only larger movements)
    blur_kernel: 5            # Gaussian blur to reduce noise (0 to disable, use odd numbers: 3,5,7,9)

cameras:
    front:
        track_changes: true
        # Override defaults for this camera
        motion_threshold: 30
        min_motion_area: 800
        blur_kernel: 7
```

**Parameters explained:**
- **motion_threshold**: Pixel brightness difference threshold (0-255). Higher values make it less sensitive to subtle changes
- **min_motion_area**: Minimum area in pixels for a contour to be considered significant motion. Increase to ignore small movements
- **blur_kernel**: Apply Gaussian blur before comparison to reduce camera sensor noise. Set to 0 to disable, or use odd numbers (3, 5, 7, 9). Higher values = more smoothing but may miss fine details

**How it works:**
1. All frames are captured and saved unconditionally
2. During video generation, if `track_changes: true`, motion detection analyzes each frame
3. Only frames with detected motion are included in the video
4. Original frames remain on disk until cleaned up by `summary_duration` setting

**Tuning tips:**
- If too many similar frames are in videos: increase `motion_threshold` or `min_motion_area`
- If important motion is missed: decrease `motion_threshold` or `min_motion_area`
- If camera has noisy sensor (many small contours): increase `blur_kernel` to 7 or 9
- Use `--test-changes --save-debug-images` to visualize what the algorithm sees

## Usage

### Run Continuously

The tool runs in a continuous loop, capturing frames at the specified interval:

```bash
python3 cctv_summarizer.py
```

Or use the provided shell script:

```bash
./run_summarizer.sh
```

### Test Single Camera

Test capture from a specific camera:

```bash
python3 cctv_summarizer.py --test-capture front
```

### Generate Videos on Demand

Generate videos from existing frames without starting the capture loop:

```bash
python3 cctv_summarizer.py --generate-videos
```

### Test Motion Detection

Test motion detection on existing frames to debug and tune thresholds:

```bash
# Test all cameras with detailed output
python3 cctv_summarizer.py --test-changes

# Test specific camera
python3 cctv_summarizer.py --test-changes front

# Save debug visualization images
python3 cctv_summarizer.py --test-changes front --save-debug-images

# Test only a range of frames (e.g., frames 10-20)
python3 cctv_summarizer.py --test-changes front --frame-range 10:20 --save-debug-images
```

The test mode shows detailed statistics for each frame comparison:
- Pixel difference statistics (mean, max)
- Percentage of changed pixels
- Number of contours detected
- Areas of significant contours
- Decision (KEEP or DISCARD)

When using `--save-debug-images`, four visualization images are created for each frame:
1. **`*_1_diff.jpg`**: Difference between frames (amplified for visibility)
2. **`*_2_thresh.jpg`**: Thresholded binary image showing changed pixels
3. **`*_3_all_contours.jpg`**: All detected contours in green
4. **`*_4_significant.jpg`**: Only significant contours in red with statistics overlay

Debug images are saved to `output_path/debug/camera_id/`.

### Use Custom Config

Specify a different configuration file:

```bash
python3 cctv_summarizer.py --config /path/to/config.yaml
```

## Running as a Service

### systemd (Linux)

1. Edit `cctv_summarizer.service` to match your paths and user
2. Copy the service file:
   ```bash
   sudo cp cctv_summarizer.service /etc/systemd/system/
   ```
3. Enable and start the service:
   ```bash
   sudo systemctl enable cctv_summarizer
   sudo systemctl start cctv_summarizer
   ```
4. Check status:
   ```bash
   sudo systemctl status cctv_summarizer
   ```

### launchd (macOS)

Create a plist file in `~/Library/LaunchAgents/`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.homeassistant.cctv-summarizer</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/igor/Projects/HomeAssistaint/scripts/ha-config/cctv_summarizer/run_summarizer.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/igor/Projects/HomeAssistaint/scripts/ha-config/cctv_summarizer</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/cctv-summarizer.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/cctv-summarizer.out</string>
</dict>
</plist>
```

Load the service:
```bash
launchctl load ~/Library/LaunchAgents/com.homeassistant.cctv-summarizer.plist
```

### Cron (Simple Alternative)

Add to crontab to run at startup:
```bash
@reboot cd /Users/igor/Projects/HomeAssistaint/scripts/ha-config/cctv_summarizer && ./run_summarizer.sh
```

## Output Structure

```
www/cctv_summaries/
├── frames/
│   ├── front/
│   │   ├── 20231115_120000.jpg
│   │   ├── 20231115_120100.jpg
│   │   └── ...
│   ├── park/
│   └── kotel/
└── videos/
    ├── front/
    │   ├── 20231115_120000.mp4
    │   └── ...
    ├── park/
    └── kotel/
```

## How It Works

1. **Frame Capture**: Every `capture_interval` seconds, the tool captures a frame from each camera using ffmpeg - **all frames are saved unconditionally**
2. **Storage**: Frames are saved with timestamps in camera-specific subdirectories
3. **Cleanup**: Old frames beyond `summary_duration` are automatically deleted
4. **Video Generation**: At the specified interval (default: hourly), a time-lapse video is generated:
   - If `track_changes` is disabled: all captured frames are included
   - If `track_changes` is enabled: frames are analyzed for motion, only frames with significant changes are included in the video
5. **Video Cleanup**: Old videos are kept at one per day to save space

### Why Motion Detection at Video Generation?

This design has several advantages:
- **No data loss**: All captured frames are preserved
- **Tune anytime**: Adjust motion detection parameters and regenerate videos from existing frames
- **Debug easily**: Use `--test-changes` to see how different parameters would affect video generation
- **Flexibility**: Disable motion detection later without losing historical data

## Troubleshooting

### Camera Connection Issues

If frame capture fails:
- Verify RTSP URL is correct
- Check network connectivity to camera
- Test RTSP stream with: `ffplay -rtsp_transport tcp "rtsp://..."`
- Ensure camera supports RTSP and is not limited by max connections

### Motion Detection Too Sensitive/Not Sensitive Enough

Use the test mode to debug and tune parameters:

```bash
# Test and see statistics
python3 cctv_summarizer.py --test-changes front

# Generate debug images to visualize
python3 cctv_summarizer.py --test-changes front --save-debug-images --frame-range 0:10
```

Then adjust parameters in `config.yaml`:
- `motion_threshold`: Pixel difference threshold (0-255, higher = less sensitive)
- `min_motion_area`: Minimum contour area in pixels (higher = only larger movements)
- `blur_kernel`: Gaussian blur size to reduce noise (0 to disable, or 3,5,7,9)

See **Motion Detection Parameters** section above for detailed tuning guidance.

### High Storage Usage

- Reduce `capture_interval` to capture less frequently
- Enable `track_changes` for motion-based capture
- Reduce `summary_duration` to retain frames for less time
- Lower video `resolution`

## Integration with Home Assistant

The tool generates HTML files with embedded video players for each camera, which can be directly integrated into Home Assistant dashboards using iframe cards.

### Why HTML Files Instead of Direct MP4?

Home Assistant's `image` element doesn't support MP4 video playback. The solution is to use iframe cards that load HTML files containing video players.

### Configuration

The tool automatically generates HTML files for each camera:
- `front.html`, `park.html`, `kotel.html` in the `videos/` directory
- Each HTML file contains a video player pointing to the latest generated video
- Videos are stored in `output_path/videos/camera_id/` (default: `../ha-config/www/cctv_summaries/videos/`)

Configure in `config.yaml`:
```yaml
config:
    iframe_template: iframe.html    # Template file for HTML generation
    create_latest_link: false       # Optional: create latest.mp4 symlink (may cause caching issues)
```

### Home Assistant Dashboard Integration

Use the **iframe card** to embed the video player in your dashboard:

```yaml
type: iframe
url: /local/cctv_summaries/videos/front.html
aspect_ratio: 16:9
```

**Note** the above static iframe may still cause cacheing issues, you then will see "white" iframe content.
Here is a solution with dynamic URL generation, which makes Home Assistant to regenerate url on each page load, and therefore caching is not a problem:

```yaml
type: custom:config-template-card
entities:
  - sensor.date_time
card:
  type: iframe
  url: ${'/local/cctv_summaries/videos/park.html?' +new Date().getTime()}
  refresh_interval: 300
```

Or create a grid of camera feeds:

```yaml
type: horizontal-stack
cards:
  - type: iframe
    url: /local/cctv_summaries/videos/front.html
    aspect_ratio: 16:9
  - type: iframe
    url: /local/cctv_summaries/videos/park.html
    aspect_ratio: 16:9
  - type: iframe
    url: /local/cctv_summaries/videos/kotel.html
    aspect_ratio: 16:9
```

### How It Works

1. When a new video is generated, the tool updates the corresponding HTML file
2. The HTML file contains a relative path to the latest video (e.g., `front/20251115_163003.mp4`)
3. Home Assistant's iframe card loads the HTML file, which plays the video
4. Each video generation updates the HTML file with the new video path
5. Browsers cache-bust automatically since the video filename includes a timestamp

### Customizing the Video Player

Edit `iframe.html` template to customize the video player:

```html
<video autoplay muted loop playsinline style="width:100%;height:100%;object-fit:cover;">
  <source src="$RELPATH" type="video/mp4">
</video>
```

Available placeholders:
- `$RELPATH` or `{{video_path}}` - relative path to the video file

### Alternative: Direct MP4 Access (Optional)

If you enable `create_latest_link: true` in config, a `latest.mp4` symlink is created for each camera. However, this may cause browser caching issues where old videos continue to display.

Direct URLs (if enabled):
- `http://your-ha-instance/local/cctv_summaries/videos/front/latest.mp4`
- `http://your-ha-instance/local/cctv_summaries/videos/park/latest.mp4`

Timestamped videos are always available:
- `http://your-ha-instance/local/cctv_summaries/videos/front/20251115_163003.mp4`

## License

MIT
