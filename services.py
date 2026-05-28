import io
import re
import asyncio
import tempfile
import os
import httpx
import yt_dlp
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from PIL import Image as PILImage
from config import RAPID_API_KEY, VIDEO_SITES

def create_pdf_from_text(text, title="Hujjat"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=18, spaceAfter=20)
    body_style = ParagraphStyle('B', parent=styles['Normal'], fontSize=12, leading=18)
    story = [Paragraph(title, title_style), Spacer(1, 0.5*cm)]
    for line in text.split('\n'):
        if line.strip():
            safe = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(safe, body_style))
        else:
            story.append(Spacer(1, 0.3*cm))
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def create_pdf_from_image(image_bytes, caption=""):
    buffer = io.BytesIO()
    img = PILImage.open(io.BytesIO(image_bytes))
    img_w, img_h = img.size
    page_size = (A4[1], A4[0]) if img_w > img_h else A4
    doc = SimpleDocTemplate(buffer, pagesize=page_size, rightMargin=0, leftMargin=0, topMargin=0, bottomMargin=0)
    page_w, page_h = page_size
    caption_height = 1*cm if caption else 0
    ratio = min(page_w / img_w, (page_h - caption_height) / img_h)
    rl_image = RLImage(io.BytesIO(image_bytes), width=img_w*ratio, height=img_h*ratio)
    story = [rl_image]
    if caption:
        styles = getSampleStyleSheet()
        cap_style = ParagraphStyle('Cap', parent=styles['Normal'], fontSize=10)
        safe_cap = caption.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(safe_cap, cap_style))
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def create_pdf_from_multiple_images(images_list, title=""):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0, leftMargin=0, topMargin=0, bottomMargin=0)
    story = []
    if title:
        styles = getSampleStyleSheet()
        story.append(Paragraph(title, styles['Title']))
        story.append(Spacer(1, 0.5*cm))
    page_w, page_h = A4
    for i, img_bytes in enumerate(images_list):
        img = PILImage.open(io.BytesIO(img_bytes))
        img_w, img_h = img.size
        ratio = min(page_w / img_w, page_h / img_h)
        rl_image = RLImage(io.BytesIO(img_bytes), width=img_w*ratio, height=img_h*ratio)
        story.append(rl_image)
        if i < len(images_list) - 1:
            story.append(PageBreak())
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

def is_video_url(url):
    return any(site in url.lower() for site in VIDEO_SITES)

async def download_youtube_rapidapi(url):
    video_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else url.split('/')[-1].split('?')[0]
    headers = {"x-rapidapi-key": RAPID_API_KEY, "x-rapidapi-host": "youtube-video-download-info.p.rapidapi.com"}
    api_url = f"https://youtube-video-download-info.p.rapidapi.com/dl?id={video_id}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(api_url, headers=headers)
        if response.status_code != 200: raise Exception(f"API Error: {response.status_code}")
        data = response.json()
        title = data.get('title', 'YouTube Video')
        link = None
        if 'link' in data:
            for fmt in data['link']:
                if isinstance(fmt, list):
                    for item in fmt:
                        if isinstance(item, dict) and item.get('type', '').startswith('video/mp4'):
                            link = item.get('href'); break
                if link: break
        if not link: raise Exception("Havola topilmadi")
        video_response = await client.get(link, timeout=120.0)
        return 'video', title, video_response.content, 'mp4'

async def download_with_ytdlp(url):
    def sync_download():
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'format': 'best[ext=mp4][filesize<50M]/best[ext=mp4]/best',
                'quiet': True, 'no_warnings': True,
                'http_headers': {'User-Agent': 'Mozilla/5.0'}
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                with open(filename, 'rb') as f: media_bytes = f.read()
                return 'image' if info.get('ext', 'mp4').lower() in ['jpg', 'jpeg', 'png'] else 'video', info.get('title', 'media'), media_bytes, info.get('ext', 'mp4')
    return await asyncio.get_event_loop().run_in_executor(None, sync_download)

async def download_media(url):
    if 'youtube.com' in url or 'youtu.be' in url:
        try: return await download_youtube_rapidapi(url)
        except: return await download_with_ytdlp(url)
    return await download_with_ytdlp(url)
