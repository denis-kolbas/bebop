from moviepy.video.io.bindings import mplfig_to_npimage
from moviepy.editor import VideoClip
from moviepy.video.VideoClip import ColorClip, TextClip
import matplotlib.pyplot as plt

duration = 2

# Create a solid color background
clip = ColorClip(size=(720, 480), color=(255, 128, 0), duration=duration)

# Add text
txt = TextClip("Test", fontsize=70, color='white')
txt = txt.set_pos('center').set_duration(duration)

# Combine clips
video = CompositeVideoClip([clip, txt])

# Write to file
video.write_videofile("test.mp4", fps=24)
