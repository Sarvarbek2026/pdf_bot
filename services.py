import io
import os
import asyncio
import tempfile
import httpx
import yt_dlp
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Image as RLImage, PageBreak
from config import RAPID_API_KEY

def create_pdf_from_images(image_paths: list, output_path: str):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=0, leftMargin=0,
                            topMargin=0, bottomMargin=0)
    story = []
    page_w, page_h = A4

    for i, path in enumerate(image_paths):
        with open(path, 'rb') as f:
            img_bytes = f.read()
        img = PILImage.open(io.BytesIO(img_bytes))
        img_w, img_h = img.size
        ratio = min(page_w / img_w, page_h / img_h)
        rl_img = RLImage(io.BytesIO(img_bytes),
                         width=img_w * ratio,
                         height=img_h * ratio)
        story.append(rl_img)
        if i < len(image_paths) - 1:
            story.append(PageBreak())

    doc.build(story)
    with open(output_path, 'wb') as f:
        f.write(buffer.getvalue())

async def download_media(url: str):
    if 'youtube.com' in url or 'youtu.be' in url:
        try:
            return await _youtube_rapidapi(url)
        except:
            pass
    return await _ytdlp(url)

async def _youtube_rapidapi(url: str):
    video_id = url.split('v=')[-1].split('&')[0] \
        if 'v=' in url else url.split('/')[-1].split('?')[0]
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "youtube-video-download-info.p.rapidapi.com"
    }
    api_url = f"https://youtube-video-download-info.p.rapidapi.com/dl?id={video_id}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(api_url, headers=headers)
        if r.status_code != 200:
            raise Exception(f"API xato: {r.status_code}")
        data = r.json()
        title = data.get('title', 'video')
        link = None
        for fmt in data.get('link', []):
            if isinstance(fmt, list):
                for item in fmt:
                    if isinstance(item, dict) and \
                       item.get('type', '').startswith('video/mp4'):
                        link = item.get('href')
                        break
            if link:
                break
        if not link:
            raise Exception("Havola topilmadi")
        video_r = await client.get(link, timeout=120.0)
        return title, video_r.content, 'mp4'

async def _ytdlp(url: str):
    def sync():
        with tempfile.TemporaryDirectory() as tmpdir:
            opts = {
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'format': 'best[ext=mp4][filesize<50M]/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'http_headers': {'User-Agent': 'Mozilla/5.0'}
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                with open(filename, 'rb') as f:
                    data = f.read()
                return info.get('title', 'video'), data, info.get('ext', 'mp4')
    return await asyncio.get_event_loop().run_in_executor(None, sync)
