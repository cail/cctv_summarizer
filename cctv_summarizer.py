#!/usr/bin/env python3
"""
CCTV Summarizer - Captures frames from RTSP cameras and generates summary videos
"""

import os
import sys
import yaml
import subprocess
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
import cv2
import numpy as np
from threading import Thread, Lock
import argparse

# Logger will be configured after loading config
logger = logging.getLogger(__name__)


class CCTVSummarizer:
    def __init__(self, config_path='config.yaml'):
        """Initialize the CCTV Summarizer with configuration"""
        self.config = self._load_config(config_path)
        self.cameras = self.config.get('cameras', {})
        self.settings = self.config.get('config', {})
        
        # Setup logging with configured level
        self._setup_logging()
        
        # Parse duration and interval
        self.summary_duration = self._parse_duration(
            self.settings.get('summary_duration', '24h')
        )
        self.capture_interval = self._parse_duration(
            self.settings.get('capture_interval', '1m')
        )
        self.video_generation_interval = self._parse_duration(
            self.settings.get('video_generation_interval', '1h')
        )
        
        # Setup paths
        self.output_path = Path(self.settings.get('output_path', './output'))
        self.frames_path = self.output_path / 'frames'
        self.videos_path = self.output_path / 'videos'
        
        # iframe template settings
        self.iframe_template_path = self.settings.get('iframe_template')
        self.iframe_template = None
        if self.iframe_template_path:
            self._load_iframe_template()
        
        # Option to create latest.mp4 symlink (disabled by default due to caching issues)
        self.create_latest_link = self.settings.get('create_latest_link', False)
        
        self._setup_directories()
        
        # Default motion detection parameters (can be overridden per camera)
        self.default_motion_threshold = self.settings.get('motion_threshold', 25)  # Pixel difference threshold
        self.default_min_motion_area = self.settings.get('min_motion_area', 500)  # Minimum area to consider as motion
        
        # Store previous frames for motion detection
        self.previous_frames = {}
        self.frame_locks = {cam_id: Lock() for cam_id in self.cameras.keys()}
        
    def _load_config(self, config_path):
        """Load YAML configuration file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            # Can't use logger here yet since it's not configured
            print(f"Failed to load config: {e}")
            sys.exit(1)
    
    def _setup_logging(self):
        """Configure logging based on config settings"""
        log_level_str = self.settings.get('log_level', 'INFO').upper()
        
        # Map string to logging level
        log_levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        
        log_level = log_levels.get(log_level_str, logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            force=True  # Reconfigure if already set
        )
        
        logger.info(f"Logging configured at {log_level_str} level")
    
    def _load_iframe_template(self):
        """Load iframe template file if specified"""
        try:
            template_path = Path(self.iframe_template_path)
            if not template_path.is_absolute():
                # Make path relative to script directory
                script_dir = Path(__file__).parent
                template_path = script_dir / template_path
            
            if template_path.exists():
                with open(template_path, 'r') as f:
                    self.iframe_template = f.read()
                logger.info(f"Loaded iframe template from {template_path}")
            else:
                logger.warning(f"Iframe template file not found: {template_path}")
        except Exception as e:
            logger.error(f"Failed to load iframe template: {e}")
    
    def _parse_duration(self, duration_str):
        """Parse duration string like '24h', '1m', '30s' into seconds"""
        unit = duration_str[-1]
        value = int(duration_str[:-1])
        
        units = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }
        
        return value * units.get(unit, 1)
    
    def _setup_directories(self):
        """Create necessary directories for storing frames and videos"""
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.frames_path.mkdir(exist_ok=True)
        self.videos_path.mkdir(exist_ok=True)
        
        for cam_id in self.cameras.keys():
            (self.frames_path / cam_id).mkdir(exist_ok=True)
            (self.videos_path / cam_id).mkdir(exist_ok=True)
    
    def capture_frame(self, cam_id, camera_config):
        """Capture a single frame from a camera using ffmpeg"""
        timestamp = datetime.now()
        filename = timestamp.strftime('%Y%m%d_%H%M%S.jpg')
        output_file = self.frames_path / cam_id / filename
        
        rtsp_url = camera_config['url']
        
        # Use ffmpeg to capture a single frame
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            '-rtsp_transport', 'tcp',  # Use TCP for more reliable streaming
            '-i', rtsp_url,
            '-frames:v', '1',  # Capture only 1 frame
            '-q:v', '2',  # Quality (2-5 is good)
            str(output_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )
            
            if result.returncode == 0 and output_file.exists():
                logger.debug(f"Captured frame from {cam_id}: {filename}")
                
                # Check if motion detection is enabled
                if camera_config.get('track_changes', False):
                    if not self._has_motion(cam_id, output_file, debug=False):
                        # No significant motion, delete the frame
                        output_file.unlink()
                        logger.debug(f"No motion detected for {cam_id}, frame deleted")
                        return None
                
                return output_file
            else:
                logger.warning(f"Failed to capture from {cam_id}: {result.stderr.decode()}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout capturing frame from {cam_id}")
            return None
        except Exception as e:
            logger.error(f"Error capturing frame from {cam_id}: {e}")
            return None
    
    def _has_motion(self, cam_id, frame_path, debug=False):
        """Detect if there's significant motion in the frame compared to previous
        
        Args:
            cam_id: Camera identifier
            frame_path: Path to the current frame
            debug: If True, output detailed debug information
        """
        # Get camera-specific thresholds or use defaults
        camera_config = self.cameras[cam_id]
        motion_threshold = camera_config.get('motion_threshold', self.default_motion_threshold)
        min_motion_area = camera_config.get('min_motion_area', self.default_min_motion_area)
        
        with self.frame_locks[cam_id]:
            try:
                # Read current frame
                current_frame = cv2.imread(str(frame_path), cv2.IMREAD_GRAYSCALE)
                
                if current_frame is None:
                    if debug:
                        logger.info(f"[{cam_id}] Could not read frame {frame_path}, keeping it")
                    return True  # Keep frame if we can't read it
                
                # If no previous frame, keep this one
                if cam_id not in self.previous_frames:
                    self.previous_frames[cam_id] = current_frame
                    if debug:
                        logger.info(f"[{cam_id}] No previous frame, keeping {frame_path.name}")
                    return True
                
                # Calculate difference
                prev_frame = self.previous_frames[cam_id]
                
                # Resize if dimensions don't match
                if current_frame.shape != prev_frame.shape:
                    prev_frame = cv2.resize(prev_frame, 
                                          (current_frame.shape[1], current_frame.shape[0]))
                
                # Compute absolute difference
                frame_diff = cv2.absdiff(prev_frame, current_frame)
                
                # Threshold the difference
                _, thresh = cv2.threshold(frame_diff, motion_threshold, 255, cv2.THRESH_BINARY)
                
                # Calculate statistics for debug output
                if debug:
                    mean_diff = np.mean(frame_diff)
                    max_diff = np.max(frame_diff)
                    pixels_changed = np.count_nonzero(thresh)
                    total_pixels = thresh.size
                    change_percentage = (pixels_changed / total_pixels) * 100
                
                # Find contours
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Get contour areas for debug
                contour_areas = [cv2.contourArea(c) for c in contours] if contours else []
                significant_contours = [area for area in contour_areas if area > min_motion_area]
                
                # Check if any contour is large enough
                has_motion = len(significant_contours) > 0
                
                if debug:
                    logger.info(f"[{cam_id}] Frame: {frame_path.name}")
                    logger.info(f"  Thresholds: motion_threshold={motion_threshold}, min_motion_area={min_motion_area}")
                    logger.info(f"  Difference stats: mean={mean_diff:.2f}, max={max_diff:.2f}")
                    logger.info(f"  Changed pixels: {pixels_changed}/{total_pixels} ({change_percentage:.2f}%)")
                    logger.info(f"  Contours found: {len(contours)}")
                    if contour_areas:
                        logger.info(f"  Contour areas: {sorted(contour_areas, reverse=True)[:5]}")  # Show top 5
                    logger.info(f"  Significant contours (>{min_motion_area}): {len(significant_contours)}")
                    logger.info(f"  Decision: {'KEEP (motion detected)' if has_motion else 'DISCARD (no motion)'}")
                
                # Update previous frame if motion detected
                if has_motion:
                    self.previous_frames[cam_id] = current_frame
                
                return has_motion
                
            except Exception as e:
                logger.error(f"Error in motion detection for {cam_id}: {e}")
                return True  # Keep frame on error
    
    def cleanup_old_frames(self, cam_id):
        """Remove frames older than summary_duration"""
        cutoff_time = datetime.now() - timedelta(seconds=self.summary_duration)
        frames_dir = self.frames_path / cam_id
        
        deleted_count = 0
        for frame_file in frames_dir.glob('*.jpg'):
            try:
                # Parse timestamp from filename
                timestamp_str = frame_file.stem  # e.g., '20231115_143022'
                frame_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                
                if frame_time < cutoff_time:
                    frame_file.unlink()
                    deleted_count += 1
            except Exception as e:
                logger.debug(f"Error processing {frame_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old frames from {cam_id}")
    
    def generate_video(self, cam_id):
        """Generate a video from captured frames for a camera"""
        frames_dir = self.frames_path / cam_id
        frames = sorted(frames_dir.glob('*.jpg'))
        
        if len(frames) < 2:
            logger.info(f"Not enough frames to generate video for {cam_id}")
            return
        
        # Generate video filename with current timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        video_format = self.settings.get('video_format', 'mp4')
        output_video = self.videos_path / cam_id / f"{timestamp}.{video_format}"
        
        # Create input file list for ffmpeg
        input_list = self.frames_path / cam_id / f"input_list_{timestamp}.txt"
        
        try:
            with open(input_list, 'w') as f:
                for frame in frames:
                    # Write absolute path to each frame
                    f.write(f"file '{frame.absolute()}'\n")
                # ffmpeg concat demuxer will display each frame for equal time
            
            # Get FPS from config (default: 25)
            video_fps = self.settings.get('video_fps', 25)
            
            # Use ffmpeg to create video
            cmd = [
                'ffmpeg',
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(input_list.absolute()),
                '-vf', f"scale=-2:{self.settings.get('resolution', '720p').rstrip('p')}",
                '-r', str(video_fps),  # Set output frame rate
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                str(output_video.absolute())
            ]
            
            logger.info(f"Generating video for {cam_id}...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )
            
            if result.returncode == 0 and output_video.exists():
                logger.info(f"Video generated: {output_video}")
                
                # Generate iframe HTML file if template is configured
                if self.iframe_template:
                    self._generate_iframe_html(cam_id, output_video)
                
                # Create/update symlink to latest video (optional, disabled by default)
                if self.create_latest_link:
                    latest_video = self.videos_path / cam_id / f"latest.{video_format}"
                    try:
                        # Remove old symlink/file if it exists
                        if latest_video.exists() or latest_video.is_symlink():
                            latest_video.unlink()
                        # Create symlink to the new video
                        latest_video.symlink_to(output_video.name)
                        logger.debug(f"Updated latest video link for {cam_id}")
                    except Exception as e:
                        logger.warning(f"Failed to create latest video link for {cam_id}: {e}")
                
                # Cleanup old videos
                self._cleanup_old_videos(cam_id)
            else:
                logger.error(f"Failed to generate video for {cam_id}: {result.stderr.decode()}")
            
        except Exception as e:
            logger.error(f"Error generating video for {cam_id}: {e}")
        finally:
            # Cleanup input list file
            if input_list.exists():
                input_list.unlink()
    
    def _generate_iframe_html(self, cam_id, video_path):
        """Generate an HTML file with iframe pointing to the video"""
        try:
            # Get relative path from videos directory to the video file
            # Format: cam_id/timestamp.mp4
            relative_video_path = f"{cam_id}/{video_path.name}"
            
            # Replace placeholders in template (support both formats)
            html_content = self.iframe_template.replace('{{video_path}}', relative_video_path)
            html_content = html_content.replace('$RELPATH', relative_video_path)
            
            # Write HTML file in videos directory with camera id as filename
            html_file = self.videos_path / f"{cam_id}.html"
            with open(html_file, 'w') as f:
                f.write(html_content)
            
            logger.info(f"Generated iframe HTML for {cam_id}: {html_file}")
        except Exception as e:
            logger.error(f"Failed to generate iframe HTML for {cam_id}: {e}")
    
    def _cleanup_old_videos(self, cam_id):
        """Remove old video files to save space (keep one video per previous day)"""
        videos_dir = self.videos_path / cam_id
        
        # Get all video files and parse their dates
        video_files = []
        for video_file in videos_dir.glob('*.mp4'):
            # Skip the 'latest.mp4' symlink
            if video_file.name.startswith('latest.'):
                continue
                
            try:
                timestamp_str = video_file.stem
                video_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                video_files.append((video_file, video_time))
            except Exception as e:
                logger.debug(f"Error processing {video_file}: {e}")
        
        if not video_files:
            return
        
        # Sort by timestamp (newest first)
        video_files.sort(key=lambda x: x[1], reverse=True)
        
        # Group videos by date
        videos_by_date = {}
        for video_file, video_time in video_files:
            date_key = video_time.date()
            if date_key not in videos_by_date:
                videos_by_date[date_key] = []
            videos_by_date[date_key].append(video_file)
        
        # For each day, keep only the newest video and delete the rest
        deleted_count = 0
        for date_key in sorted(videos_by_date.keys()):
            daily_videos = videos_by_date[date_key]
            # Keep the first (newest) video, delete the rest
            for video_file in daily_videos[1:]:
                try:
                    video_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted older same-day video: {video_file.name}")
                except Exception as e:
                    logger.error(f"Error deleting {video_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old same-day videos from {cam_id}")
    
    def capture_loop(self):
        """Main loop for capturing frames"""
        logger.info("Starting capture loop...")
        last_video_generation = {cam_id: time.time() for cam_id in self.cameras.keys()}
        
        while True:
            try:
                current_time = time.time()
                
                # Capture frames from all cameras
                for cam_id, camera_config in self.cameras.items():
                    self.capture_frame(cam_id, camera_config)
                    self.cleanup_old_frames(cam_id)
                    
                    # Check if it's time to generate video
                    if current_time - last_video_generation[cam_id] >= self.video_generation_interval:
                        Thread(target=self.generate_video, args=(cam_id,)).start()
                        last_video_generation[cam_id] = current_time
                
                # Wait for next capture interval
                time.sleep(self.capture_interval)
                
            except KeyboardInterrupt:
                logger.info("Stopping capture loop...")
                break
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(5)  # Wait before retrying


    def test_changes(self, cam_id=None):
        """Test motion detection on existing frames with debug output
        
        Args:
            cam_id: Specific camera to test, or None for all cameras
        """
        cameras_to_test = [cam_id] if cam_id else list(self.cameras.keys())
        
        for camera_id in cameras_to_test:
            if camera_id not in self.cameras:
                logger.error(f"Camera '{camera_id}' not found in config")
                continue
            
            camera_config = self.cameras[camera_id]
            frames_dir = self.frames_path / camera_id
            
            if not frames_dir.exists():
                logger.warning(f"No frames directory found for {camera_id}")
                continue
            
            frames = sorted(frames_dir.glob('*.jpg'))
            
            if len(frames) < 2:
                logger.warning(f"Not enough frames to test for {camera_id} (found {len(frames)})")
                continue
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing motion detection for camera: {camera_id}")
            logger.info(f"Total frames: {len(frames)}")
            logger.info(f"Track changes enabled: {camera_config.get('track_changes', False)}")
            logger.info(f"{'='*60}\n")
            
            # Reset previous frame for this camera
            if camera_id in self.previous_frames:
                del self.previous_frames[camera_id]
            
            kept_count = 0
            discarded_count = 0
            
            for i, frame_path in enumerate(frames):
                logger.info(f"\n--- Processing frame {i+1}/{len(frames)} ---")
                has_motion = self._has_motion(camera_id, frame_path, debug=True)
                
                if has_motion:
                    kept_count += 1
                else:
                    discarded_count += 1
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Summary for {camera_id}:")
            logger.info(f"  Total frames: {len(frames)}")
            logger.info(f"  Would keep: {kept_count} ({kept_count/len(frames)*100:.1f}%)")
            logger.info(f"  Would discard: {discarded_count} ({discarded_count/len(frames)*100:.1f}%)")
            logger.info(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='CCTV Summarizer - Capture and summarize RTSP camera feeds')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--generate-videos', action='store_true', help='Generate videos now and exit')
    parser.add_argument('--test-capture', metavar='CAMERA_ID', help='Test capture from a single camera')
    parser.add_argument('--test-changes', metavar='CAMERA_ID', nargs='?', const='ALL',
                        help='Test motion detection on existing frames. Specify camera ID or omit for all cameras')
    
    args = parser.parse_args()
    
    summarizer = CCTVSummarizer(args.config)
    
    if args.test_changes:
        # Test motion detection on existing frames
        if args.test_changes == 'ALL':
            logger.info("Testing motion detection on all cameras...")
            summarizer.test_changes()
        elif args.test_changes in summarizer.cameras:
            logger.info(f"Testing motion detection on {args.test_changes}...")
            summarizer.test_changes(args.test_changes)
        else:
            logger.error(f"Camera '{args.test_changes}' not found in config")
            logger.info(f"Available cameras: {', '.join(summarizer.cameras.keys())}")
        return
    
    if args.test_capture:
        # Test capture from specific camera
        if args.test_capture in summarizer.cameras:
            camera_config = summarizer.cameras[args.test_capture]
            logger.info(f"Testing capture from {args.test_capture}...")
            result = summarizer.capture_frame(args.test_capture, camera_config)
            if result:
                logger.info(f"Success! Frame saved to: {result}")
            else:
                logger.error("Capture failed")
        else:
            logger.error(f"Camera '{args.test_capture}' not found in config")
            logger.info(f"Available cameras: {', '.join(summarizer.cameras.keys())}")
        return
    
    if args.generate_videos:
        # Generate videos for all cameras and exit
        logger.info("Generating videos for all cameras...")
        for cam_id in summarizer.cameras.keys():
            summarizer.generate_video(cam_id)
        return
    
    # Run continuous capture loop
    summarizer.capture_loop()


if __name__ == '__main__':
    main()
