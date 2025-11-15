# CCTV Summarizer

A Python tool for capturing frames from RTSP cameras and generating time-lapse summary videos. Ideal for monitoring multiple cameras with activity-focused recording using motion detection.

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
- **track_changes**: Enable motion detection for a camera (saves storage by only keeping frames with activity)

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

1. **Frame Capture**: Every `capture_interval` seconds, the tool captures a frame from each camera using ffmpeg
2. **Motion Detection** (optional): If `track_changes` is enabled, frames are analyzed for motion. Frames without significant changes are discarded
3. **Storage**: Frames are saved with timestamps in camera-specific subdirectories
4. **Cleanup**: Old frames beyond `summary_duration` are automatically deleted
5. **Video Generation**: At the specified interval (default: hourly), a time-lapse video is generated from all captured frames
6. **Video Cleanup**: Old videos (older than 7 days) are automatically removed

## Troubleshooting

### Camera Connection Issues

If frame capture fails:
- Verify RTSP URL is correct
- Check network connectivity to camera
- Test RTSP stream with: `ffplay -rtsp_transport tcp "rtsp://..."`
- Ensure camera supports RTSP and is not limited by max connections

### Motion Detection Too Sensitive/Not Sensitive Enough

Adjust parameters in `cctv_summarizer.py`:
- `motion_threshold`: Pixel difference threshold (default: 25)
- `min_motion_area`: Minimum area in pixels to consider as motion (default: 500)

### High Storage Usage

- Reduce `capture_interval` to capture less frequently
- Enable `track_changes` for motion-based capture
- Reduce `summary_duration` to retain frames for less time
- Lower video `resolution`

## Integration with Home Assistant

The videos are saved to `../www/cctv_summaries/` which maps to Home Assistant's web root. 

Each camera has a **stable `latest.mp4` link** that always points to the most recently generated video, making it easy to embed in dashboards:

```yaml
# Home Assistant Lovelace card example
type: picture-elements
camera_image: camera.front_door
elements:
  - type: image
    entity: camera.front_door
    tap_action:
      action: url
      url_path: /local/cctv_summaries/videos/front/latest.mp4
```

Direct URL access:
- Front camera: `http://your-ha-instance/local/cctv_summaries/videos/front/latest.mp4`
- Park camera: `http://your-ha-instance/local/cctv_summaries/videos/park/latest.mp4`
- Kotel camera: `http://your-ha-instance/local/cctv_summaries/videos/kotel/latest.mp4`

Timestamped videos are also available at:
- `http://your-ha-instance/local/cctv_summaries/videos/front/20231115_120000.mp4`

## License

MIT
