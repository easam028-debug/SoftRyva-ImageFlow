# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 SoftRyva Development contributors
# This file is provided without warranty. See LICENSE.

"""Reusable SoftRyva wizard branding generator for Inno Setup 6.6+.

Only product.json and its application icon need to change for future apps.
Generates branded PNGs with the required Inno Setup 164:314 and 1:1 ratios.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def font(size: int, bold: bool = False):
    candidates = (
        [r'C:\Windows\Fonts\segoeuib.ttf', r'C:\Windows\Fonts\arialbd.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if bold
        else [r'C:\Windows\Fonts\segoeui.ttf', r'C:\Windows\Fonts\arial.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def rgb(hexcode):
    return tuple(int(hexcode.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))


def fit_text(draw, value, max_width, start, bold=True):
    for sz in range(start, 10, -2):
        f=font(sz,bold)
        if draw.textbbox((0,0),value,font=f)[2] <= max_width:
            return f
    return font(12, bold)


def create_art(config, destination):
    cfg_path=Path(config).resolve()
    c=json.loads(cfg_path.read_text(encoding='utf-8'))
    base=cfg_path.parent
    icon_path=(base/c['icon']).resolve()
    if not icon_path.exists():
        raise FileNotFoundError(f'Expected product icon: {icon_path}')
    output=Path(destination);output.mkdir(parents=True,exist_ok=True)
    brand=c['brand'];product=c['product'];tagline=c['tagline']
    blue=rgb(c.get('primary','#0A91FA'));orange=rgb(c.get('accent','#FF992B'))
    navy=(5,17,34); white=(244,250,255);muted=(160,186,210)
    W,H=492,942   # exact 164:314 aspect ratio, high DPI
    art=Image.new('RGB',(W,H))
    d=ImageDraw.Draw(art)
    for y in range(H):
        t=y/(H-1)
        d.line((0,y,W,y),fill=(int(5+3*t),int(17+11*t),int(34+24*t)))
    # Curving brand ribbons behind product identity, shared across all applications.
    d.ellipse((-300,70,760,1080),outline=(12,72,117),width=9)
    d.arc((-310,290,805,1110),205,335,fill=blue,width=14)
    d.arc((-260,400,750,1220),205,310,fill=orange,width=10)
    d.rounded_rectangle((44,62,448,162),radius=23,fill=(13,41,67),outline=(25,106,157),width=2)
    d.text((68,74),brand,font=font(48,True),fill=white)
    d.text((70,132),'ORIGINAL DESKTOP SOFTWARE',font=font(15,True),fill=muted)
    # Product icon is THE program-specific visual identity.
    icon=Image.open(icon_path).convert('RGBA').resize((288,288),Image.Resampling.LANCZOS)
    glow=Image.new('RGBA',(410,410),(0,0,0,0))
    g=ImageDraw.Draw(glow)
    g.ellipse((44,44,366,366),fill=(*blue,75))
    glow=glow.filter(ImageFilter.GaussianBlur(38))
    art.paste(glow,(41,205),glow)
    art.paste(icon,(102,270),icon)
    d=ImageDraw.Draw(art)
    d.rounded_rectangle((44,619,448,829),radius=22,fill=(11,33,54),outline=(19,74,109),width=2)
    name_font=fit_text(d,product,366,53)
    name_w=d.textbbox((0,0),product,font=name_font)[2]
    d.text(((W-name_w)//2,644),product,font=name_font,fill=white)
    d.rounded_rectangle((160,719,332,726),radius=3,fill=orange)
    lines=[]
    words=tagline.split()
    line=''
    for word in words:
        trial=(line+' '+word).strip()
        if d.textbbox((0,0),trial,font=font(17))[2] > 358 and line:
            lines.append(line);line=word
        else:line=trial
    if line:lines.append(line)
    for k,text in enumerate(lines[:3]):
        tw=d.textbbox((0,0),text,font=font(17))[2]
        d.text(((W-tw)//2,744+k*25),text,font=font(17),fill=muted)
    d.text((61,870),'Powered by '+brand,font=font(21,True),fill=white)
    d.text((61,906),'PRIVATE  •  LOCAL  •  RELIABLE',font=font(15,True),fill=blue)
    art.save(output/'welcome.png',optimize=True)

    small=Image.new('RGBA',(180,180),(*navy,255))
    sd=ImageDraw.Draw(small)
    sd.rounded_rectangle((3,3,176,176),radius=30,fill=(10,38,63,255),outline=(*blue,255),width=4)
    sic=Image.open(icon_path).convert('RGBA').resize((144,144),Image.Resampling.LANCZOS)
    small.alpha_composite(sic,(18,18))
    small.save(output/'small.png',optimize=True)
    print(f'Generated {output/"welcome.png"} and {output/"small.png"}')


if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('--config',required=True)
    cli.add_argument('--output',required=True)
    args=cli.parse_args()
    create_art(args.config,args.output)
