# Demo movie

`pi-agents-intro.mp4` is rendered from genuine Pi model event streams captured
by `capture_demo.py`. The renderer shortens only the wait before each model's
first token; the token-delta timing after that point is replayed at 1×.

```bash
python3 demo/capture_demo.py
python3 demo/render_demo.py
```

The capture step invokes the public aliases through Pi's JSON output mode with
tools disabled, records every text delta with its arrival time, and stores only
that path-free evidence in `demo/captures/`. The movie recreates the interactive terminal
presentation around those streams so the slow model-loading gaps can be edited
without accelerating the model's answer.

`pi-agents-intro.gif` is the README-friendly 1280×720, 10 fps version of the
same movie. Regenerate it with:

```bash
ffmpeg -i demo/pi-agents-intro.mp4 \
  -vf "fps=10,scale=1280:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=64:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" \
  -loop 0 demo/pi-agents-intro.gif
```
