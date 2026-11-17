# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 SoftRyva Development contributors
# This file is provided without warranty. See LICENSE.

import tempfile
import unittest
from pathlib import Path

from PIL import Image, features
from core import Options, optimize_image


class TestImageFlowCore(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.root=Path(self.dir.name)
        self.output=self.root/'processed'
        self.src=self.root/'test.png'
        im=Image.new('RGBA',(120,120),(40,80,220,100))
        im.save(self.src)

    def tearDown(self):
        self.dir.cleanup()

    def test_jpeg_converts_alpha_to_white(self):
        original=self.src.read_bytes()
        r=optimize_image(self.src,Options(str(self.output),'JPEG',70))
        self.assertEqual(Path(r.target).suffix,'.jpg')
        self.assertEqual(Path(r.source).read_bytes(),original)
        with Image.open(r.target) as im:
            self.assertEqual(im.format,'JPEG')
            self.assertEqual(im.mode,'RGB')

    def test_png_is_lossless(self):
        r=optimize_image(self.src,Options(str(self.output),'PNG',85))
        with Image.open(r.target) as im, Image.open(self.src) as src:
            self.assertEqual(im.mode,'RGBA')
            self.assertEqual(im.tobytes(),src.tobytes())

    @unittest.skipUnless(features.check('webp'),'WebP not present in Pillow')
    def test_webp(self):
        r=optimize_image(self.src,Options(str(self.output),'WEBP',80))
        with Image.open(r.target) as im:
            self.assertEqual(im.format,'WEBP')
            self.assertEqual(im.size,(120,120))

    def test_does_not_overwrite_previous_outputs(self):
        opts=Options(str(self.output),'JPEG',75)
        first=optimize_image(self.src,opts)
        second=optimize_image(self.src,opts)
        self.assertNotEqual(first.target,second.target)
        self.assertTrue(Path(first.target).exists())

    def test_source_must_be_supported(self):
        txt=self.root/'test.txt';txt.write_text('text')
        with self.assertRaises(ValueError):
            optimize_image(txt,Options(str(self.output)))

    def test_bad_quality_rejected(self):
        with self.assertRaises(ValueError):
            optimize_image(self.src,Options(str(self.output),quality=101))

    def test_output_in_source_folder_safe(self):
        r=optimize_image(self.src,Options(str(self.root),'PNG'))
        self.assertNotEqual(str(self.src),r.target)
        self.assertTrue(self.src.exists())

    def test_exif_removed_by_default(self):
        jpg=self.root/'private.jpg'
        im=Image.new('RGB',(100,100),'blue')
        exif=Image.Exif();exif[271]='Private Camera Model'
        im.save(jpg,exif=exif)
        r=optimize_image(jpg,Options(str(self.output),'JPEG',75,False))
        with Image.open(r.target) as x:
            self.assertIsNone(x.getexif().get(271))


if __name__=='__main__':unittest.main()


class TestSmartCompression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / 'output'

    def tearDown(self):
        self.temp.cleanup()

    @unittest.skipUnless(features.check('webp'), 'WebP not present in Pillow')
    def test_auto_preserves_transparency(self):
        source = self.root / 'transparent.png'
        im = Image.new('RGBA', (110, 130), (30, 100, 200, 0))
        im.putpixel((20, 20), (120, 200, 130, 190))
        im.save(source)
        r = optimize_image(source, Options(str(self.output), output_format='Auto',
                                           smart=True, smart_preset='Higher Quality'))
        self.assertIn(r.format, ('WEBP', 'PNG'))
        with Image.open(r.target) as saved:
            self.assertEqual(saved.size, im.size)
            self.assertIn('A', saved.convert('RGBA').getbands())
            self.assertEqual(saved.convert('RGBA').getpixel((0, 0))[3], 0)

    @unittest.skipUnless(features.check('webp'), 'WebP not present in Pillow')
    def test_auto_rgb_is_valid_and_no_overwrite(self):
        source = self.root / 'photo.jpg'
        im = Image.new('RGB', (260, 130))
        for x in range(im.width):
            for y in range(im.height):
                im.putpixel((x,y), (x%256, (x+y)%256, 55))
        im.save(source, quality=94)
        source_bytes = source.read_bytes()
        o = Options(str(self.output), output_format='Auto', smart=True)
        first = optimize_image(source, o)
        second = optimize_image(source, o)
        self.assertIn(first.format, ('JPEG', 'PNG', 'WEBP'))
        self.assertNotEqual(first.target, second.target)
        self.assertEqual(source.read_bytes(), source_bytes)
        with Image.open(first.target) as result:
            result.verify()

    def test_smart_png_is_still_lossless(self):
        source = self.root/'alpha.png'
        img = Image.new('RGBA', (87, 99), (21, 89, 132, 84))
        img.save(source)
        result = optimize_image(source, Options(str(self.output), output_format='PNG',
                smart=True, smart_preset='Smaller File'))
        with Image.open(result.target) as saved:
            self.assertEqual(saved.tobytes(), img.tobytes())

    def test_unknown_smart_preset_rejected(self):
        with self.assertRaises(ValueError):
            Options(str(self.output), smart_preset='Faster than light').validate()
