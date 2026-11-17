# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 SoftRyva Development contributors
"""Generate temporary *source-review* icons without external brand assets.

These simple original shapes are licensed under GPL-3.0-only as part of the code.
They are NOT the approved final SoftRyva logo. Replace only after rights review.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

def generate():
    HERE.mkdir(parents=True, exist_ok=True)
    n = 512
    img = Image.new('RGBA',(n,n),(0,0,0,0))
    d=ImageDraw.Draw(img)
    d.rounded_rectangle((18,18,n-18,n-18),radius=116,fill='#08213d',outline='#13bfff',width=15)
    d.rounded_rectangle((72,112,440,385),radius=48,fill='#123c68',outline='#5ed9ff',width=7)
    d.ellipse((112,153,183,224),fill='#ffab39')
    d.polygon([(94,331),(192,242),(256,301),(332,205),(414,331)],fill='#11b5f1')
    d.arc((135,86,401,416),start=45,end=300,fill='#ff9d29',width=22)
    d.polygon([(381,106),(410,117),(387,146)],fill='#ff9d29')
    img.save(HERE/'icon.png')
    img.save(HERE/'logo.png')
    sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]
    img.save(HERE/'ImageFlow.ico',sizes=sizes)
    print('Generated review-only icons. Do not substitute for final approved branding.')

if __name__=='__main__':
    generate()
