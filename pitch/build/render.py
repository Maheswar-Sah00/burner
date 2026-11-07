"""Render the lablab cover image and the slide deck from the HTML sources in this folder.

    python pitch/build/render.py            # cover + slides
    python pitch/build/render.py cover      # cover only
    python pitch/build/render.py slides     # slides only

Outputs: pitch/cover.png, pitch/Burner-slides.pdf, and per-slide previews in pitch/build/preview/.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

HERE = pathlib.Path(__file__).resolve().parent
PITCH = HERE.parent


async def open_page(browser, name):
    ctx = await browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    page = await ctx.new_page()
    await page.goto((HERE / name).as_uri(), wait_until="networkidle")
    await page.evaluate("document.fonts.ready")
    await page.wait_for_timeout(600)
    return page


async def cover(browser):
    page = await open_page(browser, "cover.html")
    await page.screenshot(path=str(PITCH / "cover.png"), clip={"x": 0, "y": 0, "width": 1920, "height": 1080})
    print("wrote", PITCH / "cover.png")


async def slides(browser):
    """Screenshot every slide at 2x and assemble the PDF from those images, so the PDF looks exactly like
    the previews (Chrome's print engine drops the CSS masks on the halftone fields). Links stay clickable."""
    import io

    import fitz  # PyMuPDF
    from PIL import Image

    ctx = await browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=2)
    page = await ctx.new_page()
    await page.goto((HERE / "slides.html").as_uri(), wait_until="networkidle")
    await page.evaluate("document.fonts.ready")
    await page.wait_for_timeout(600)
    out = HERE / "preview"
    out.mkdir(exist_ok=True)
    doc = fitz.open()
    for i, el in enumerate(await page.query_selector_all("section.slide"), 1):
        png = await el.screenshot()
        Image.open(io.BytesIO(png)).resize((1920, 1080), Image.LANCZOS).save(out / f"slide-{i}.png")
        jpg = io.BytesIO()
        Image.open(io.BytesIO(png)).convert("RGB").save(jpg, "JPEG", quality=90, optimize=True)
        pdf_page = doc.new_page(width=1920, height=1080)
        pdf_page.insert_image(pdf_page.rect, stream=jpg.getvalue())
        box = await el.bounding_box()
        for a in await el.query_selector_all("[data-href]"):
            b = await a.bounding_box()
            r = fitz.Rect(b["x"] - box["x"], b["y"] - box["y"], b["x"] - box["x"] + b["width"], b["y"] - box["y"] + b["height"])
            pdf_page.insert_link({"kind": fitz.LINK_URI, "from": r, "uri": await a.get_attribute("data-href")})
    doc.set_metadata({"title": "Burner: run the take-home before it runs you", "author": "Maheswar-Sah00"})
    doc.save(PITCH / "Burner-slides.pdf", deflate=True)
    print("wrote", PITCH / "Burner-slides.pdf", "and previews in", out)


async def main(which):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        if which in ("all", "cover"):
            await cover(browser)
        if which in ("all", "slides"):
            await slides(browser)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "all"))
