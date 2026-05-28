import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RAPID_API_KEY = os.environ.get("RAPID_API_KEY")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "smart_pdf_video_bot")

VIDEO_SITES = [
    'youtube.com', 'youtu.be',
    'instagram.com', 'tiktok.com', 'vm.tiktok.com',
    'pinterest.com', 'pin.it',
    'facebook.com', 'fb.watch',
    'twitter.com', 'x.com'
]
