from moviepy.editor import ColorClip, TextClip, CompositeVideoClip

# Create a simple 2-second clip
clip = ColorClip(size=(720, 480), color=(255, 128, 0), duration=2)
txt = TextClip("Test", fontsize=70, color='white')
txt = txt.set_pos('center').set_duration(2)
video = CompositeVideoClip([clip, txt])
video.write_videofile("test.mp4", fps=24)
