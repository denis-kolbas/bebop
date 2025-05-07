from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ColorClip
import logging

logging.basicConfig(level=logging.INFO)

# Create base clip
clip = ColorClip(size=(720, 480), color=(255, 128, 0)).with_duration(2)

# Create text
txt = TextClip(
    text="Test",
    font="Arial",
    font_size=70,
    color='white'
).with_duration(2).with_position('center')

# Combine
video = CompositeVideoClip([clip, txt])
video.write_videofile("test.mp4")
