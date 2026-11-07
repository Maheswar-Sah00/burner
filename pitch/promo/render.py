"""Render pitch/promo/promo.html to MP4 (or stills).
python pitch/promo/render.py stills 1.5 6.2 ...   -> PNGs in the scratch dir given by OUT env
python pitch/promo/render.py video out.mp4        -> 30 fps H.264
"""
import os, subprocess, sys, pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
FFMPEG = r"C:\Users\butu1\AppData\Local\Programs\Python\Python312\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
FPS = 30

def main():
    mode = sys.argv[1]
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto((HERE / "promo.html").as_uri())
        pg.wait_for_function("window.READY === true", timeout=60000)
        if mode == "stills":
            out = pathlib.Path(os.environ["OUT"]); out.mkdir(parents=True, exist_ok=True)
            for t in sys.argv[2:]:
                pg.evaluate(f"renderAt({float(t)})")
                pg.screenshot(path=str(out / f"t{float(t):05.2f}.png"))
        else:
            dst = sys.argv[2]
            dur = pg.evaluate("window.DURATION")
            ff = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                                   "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
                                   "-movflags", "+faststart", dst], stdin=subprocess.PIPE)
            for f in range(int(dur * FPS)):
                pg.evaluate(f"renderAt({f / FPS})")
                ff.stdin.write(pg.screenshot(type="png"))
            ff.stdin.close(); ff.wait()
            print("wrote", dst)
        b.close()

if __name__ == "__main__":
    main()
