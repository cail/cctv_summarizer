
# cctv_summarizer

This tool should capture a frame from a set of predefined rtsp cameras.
each camera in a set should have a short id.

frames are organized in subfolders for storage, total capture period is limited (default - 24 hours).
So Old captures are deleted.

With some biggerr period, each hour by default, tool also generates a video from the already captured set of images for each camera.

The idea is to collect an aggregatted view from CCTVs for a quick overview.

An additional optional logic is to only use images when some significant changes/movements are detected. 

So it will be a summary overview of Activities.

# tools and dependencies
Logic is written in python, because potentially we want to process image differences.

Still, rtsp capture and video generation is probably easier to do via calling ffmpeg.
