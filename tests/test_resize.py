# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 SoftRyva Development contributors
# This file is provided without warranty. See LICENSE.

"""Regression and Image Resizer tests for SoftRyva ImageFlow v0.3.0."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageOps
from core import Options, optimize_image, resize_dimensions


class ResizerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out = self.root / 'output'
        self.photo = self.root / 'photo.jpg'
        Image.new('RGB', (600, 400), (40, 130, 220)).save(self.photo, quality=97)
        self.default = Options(str(self.out), output_format='JPEG', smart=False)

    def tearDown(self):
        self.tmp.cleanup()

    def opts(self, **kwargs):
        return replace(self.default, resize_enabled=True, **kwargs)

    def test_v02_default_is_not_resized(self):
        result = optimize_image(self.photo, self.default)
        with Image.open(result.target) as saved:
            self.assertEqual(saved.size, (600, 400))
        self.assertEqual((result.target_width, result.target_height), (600, 400))

    def test_width_only_keeps_proportions(self):
        r = optimize_image(self.photo, self.opts(resize_width=300))
        with Image.open(r.target) as im:
            self.assertEqual(im.size, (300, 200))
        self.assertEqual((r.source_width, r.source_height, r.target_width, r.target_height),
                         (600,400,300,200))

    def test_height_only_keeps_proportions(self):
        r = optimize_image(self.photo, self.opts(resize_height=100))
        with Image.open(r.target) as im:
            self.assertEqual(im.size, (150,100))

    def test_fit_bounding_box_keeps_proportions(self):
        opts=self.opts(resize_width=200, resize_height=200)
        self.assertEqual(resize_dimensions((600,400),opts),(200,133))

    def test_unlocked_pixels_can_stretch(self):
        r=optimize_image(self.photo,self.opts(resize_width=200,resize_height=200,resize_lock_aspect=False))
        with Image.open(r.target) as im:
            self.assertEqual(im.size,(200,200))

    def test_percent_mode_and_original_unchanged(self):
        original=self.photo.read_bytes()
        r=optimize_image(self.photo,self.opts(resize_mode='Percent',resize_percent=25))
        with Image.open(r.target) as im:
            self.assertEqual(im.size,(150,100))
        self.assertEqual(self.photo.read_bytes(),original)

    def test_enlargement_disabled_by_default(self):
        opts=self.opts(resize_width=1200)
        self.assertEqual(resize_dimensions((600,400),opts),(600,400))
        opts=self.opts(resize_mode='Percent',resize_percent=200)
        self.assertEqual(resize_dimensions((600,400),opts),(600,400))

    def test_enlargement_explicit(self):
        opts=self.opts(resize_mode='Percent',resize_percent=150,resize_allow_upscale=True)
        self.assertEqual(resize_dimensions((600,400),opts),(900,600))

    def test_metadata_after_resize(self):
        src=self.root/'metadata.jpg'
        im=Image.new('RGB',(600,400), 'yellow')
        exif=Image.Exif()
        exif[271]='Demo Camera'
        exif[40962]=600
        exif[40963]=400
        im.save(src,exif=exif)
        r=optimize_image(src, self.opts(resize_width=300,keep_metadata=True))
        with Image.open(r.target) as saved:
            self.assertEqual(saved.getexif().get(271),'Demo Camera')
            self.assertEqual(saved.getexif().get(40962),300)
            self.assertEqual(saved.getexif().get(40963),200)

    def test_alpha_remains_alpha_when_resized_png(self):
        source=self.root/'transparent.png'
        im=Image.new('RGBA',(400,240),(3,60,190,0))
        im.putpixel((30,30),(240,100,50,200))
        im.save(source)
        r=optimize_image(source,replace(self.opts(resize_width=200),output_format='PNG',smart=True))
        with Image.open(r.target) as saved:
            self.assertEqual(saved.size,(200,120))
            self.assertEqual(saved.convert('RGBA').getpixel((0,0))[3],0)

    def test_batch_images_keep_own_ratios(self):
        second=self.root/'portrait.webp'
        Image.new('RGB',(200,600),'navy').save(second)
        opts=self.opts(resize_width=150,output_format='Auto',smart=True)
        a=optimize_image(self.photo,opts)
        b=optimize_image(second,opts)
        self.assertEqual((a.target_width,a.target_height),(150,100))
        self.assertEqual((b.target_width,b.target_height),(150,450))
        self.assertNotEqual(a.target,b.target)

    def test_invalid_configurations(self):
        for kw in (
            {'resize_width':None},
            {'resize_width':0},
            {'resize_width':30001},
            {'resize_width':100,'resize_lock_aspect':False},
            {'resize_mode':'Percent','resize_percent':0},
            {'resize_mode':'Percent','resize_percent':401},
            {'resize_mode':'Other','resize_width':100},
        ):
            with self.subTest(**kw),self.assertRaises(ValueError):
                self.opts(**kw).validate()

    def test_output_existing_never_overwritten(self):
        opts=self.opts(resize_width=150)
        a=optimize_image(self.photo,opts)
        b=optimize_image(self.photo,opts)
        self.assertNotEqual(a.target,b.target)
        self.assertEqual(Path(a.target).stat().st_size,a.target_size)

    def test_exif_orientation_resized_in_visible_orientation(self):
        source=self.root/'rotated.jpg'
        img=Image.new('RGB',(300,600),'orange')
        exif=Image.Exif()
        exif[274]=6  # display it as 600x300
        img.save(source,exif=exif)
        result=optimize_image(source,self.opts(resize_width=150,keep_metadata=True))
        self.assertEqual((result.source_width,result.source_height),(600,300))
        with Image.open(result.target) as saved:
            self.assertEqual(saved.size,(150,75))
            self.assertIn(saved.getexif().get(274), (None, 1))


if __name__ == '__main__':
    unittest.main()
