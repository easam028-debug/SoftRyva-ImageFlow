# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 SoftRyva Development contributors
# This file is provided without warranty. See LICENSE.

"""Offline image conversion and optimization for SoftRyva ImageFlow.

Smart Compression is an actual encoder-selection routine, not an AI model:
it evaluates multiple encodings, checks approximate image fidelity, and selects
one of the acceptable candidates with the lowest file size. A lossless PNG
candidate is also considered in Auto mode. Files never leave the machine.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
import math
import os
import tempfile
import time
from typing import Literal

from PIL import Image, ImageChops, ImageOps, ImageStat

Format = Literal['Original', 'Auto', 'JPEG', 'PNG', 'WEBP']
ACCEPTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
EXTENSIONS = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}
PRESETS = ('Smaller File', 'Balanced', 'Higher Quality')
MAX_RESIZE_DIMENSION = 30000
MAX_RESIZE_PIXELS = 100_000_000


@dataclass(frozen=True)
class Options:
    output_dir: str
    output_format: Format = 'Original'
    quality: int = 75
    keep_metadata: bool = False
    filename_suffix: str = '_optimized'
    smart: bool = True
    smart_preset: str = 'Balanced'
    resize_enabled: bool = False
    resize_mode: Literal['Pixels', 'Percent'] = 'Pixels'
    resize_width: int | None = None
    resize_height: int | None = None
    resize_percent: int = 50
    resize_lock_aspect: bool = True
    resize_allow_upscale: bool = False

    def validate(self) -> None:
        if self.output_format not in ('Original', 'Auto', 'JPEG', 'PNG', 'WEBP'):
            raise ValueError('Invalid output format.')
        if not isinstance(self.quality, int) or not (1 <= self.quality <= 100):
            raise ValueError('Quality must be between 1 and 100.')
        if self.smart_preset not in PRESETS:
            raise ValueError('Invalid Smart Compression preset.')
        if not isinstance(self.output_dir, str) or not self.output_dir.strip():
            raise ValueError('Select an output folder.')
        if self.resize_mode not in ('Pixels', 'Percent'):
            raise ValueError('Resize mode must be Pixels or Percent.')
        if self.resize_enabled:
            if self.resize_mode == 'Pixels':
                if self.resize_width is None and self.resize_height is None:
                    raise ValueError('Enter a target width or height in pixels.')
                for dimension in (self.resize_width, self.resize_height):
                    if dimension is not None and (type(dimension) is not int or not 1 <= dimension <= MAX_RESIZE_DIMENSION):
                        raise ValueError(f'Width and height must be 1–{MAX_RESIZE_DIMENSION:,} pixels.')
                if not self.resize_lock_aspect and (self.resize_width is None or self.resize_height is None):
                    raise ValueError('Enter both width and height when aspect ratio is unlocked.')
            elif type(self.resize_percent) is not int or not 1 <= self.resize_percent <= 400:
                raise ValueError('Resize percentage must be between 1 and 400.')
        if any(ch in self.filename_suffix for ch in '<>:"/\\|?*') or '..' in self.filename_suffix:
            raise ValueError('Invalid file name suffix.')


@dataclass
class Result:
    source: str
    target: str
    source_size: int
    target_size: int
    elapsed_seconds: float
    format: str
    source_width: int = 0
    source_height: int = 0
    target_width: int = 0
    target_height: int = 0

    @property
    def reduction_percent(self) -> float:
        return 100.0 * (1 - self.target_size / self.source_size) if self.source_size else 0.0

    def as_dict(self) -> dict:
        return {**asdict(self), 'reduction_percent': round(self.reduction_percent, 2)}


def readable_bytes(byte_count: int) -> str:
    value = float(byte_count)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if abs(value) < 1024 or unit == 'GB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.2f} {unit}'
        value /= 1024
    return f'{value:.2f} GB'


def _source_format(im: Image.Image) -> str:
    fmt = (im.format or '').upper()
    if fmt in EXTENSIONS:
        return fmt
    raise ValueError('Unsupported image format. Choose JPEG, PNG or WEBP.')


def _has_alpha(image: Image.Image) -> bool:
    return 'A' in image.getbands() or 'transparency' in image.info


def _converted(image: Image.Image, fmt: str) -> Image.Image:
    if fmt == 'JPEG':
        if _has_alpha(image):
            rgba = image.convert('RGBA')
            white = Image.new('RGB', rgba.size, '#ffffff')
            white.paste(rgba, mask=rgba.getchannel('A'))
            return white
        return image.convert('RGB') if image.mode not in ('RGB', 'L') else image.copy()
    if fmt == 'WEBP':
        return image.convert('RGBA' if _has_alpha(image) else 'RGB')
    if image.mode in ('CMYK', 'P', '1'):
        return image.convert('RGBA' if _has_alpha(image) else 'RGB')
    return image.copy()


def _destination(base: Path, suffix: str, extension: str) -> Path:
    candidate = base.with_name(base.name + suffix).with_suffix(extension)
    number = 2
    while candidate.exists():
        candidate = base.with_name(f'{base.name}{suffix}_{number}').with_suffix(extension)
        number += 1
    return candidate


def _encoded(image: Image.Image, fmt: str, quality: int, keep_metadata: bool,
             original_icc: bytes | None, exif: bytes | None) -> bytes:
    converted = _converted(image, fmt)
    try:
        save_opts = {}
        if fmt == 'JPEG':
            save_opts.update(quality=quality, optimize=True, progressive=True, subsampling=0 if quality>=95 else 2)
        elif fmt == 'WEBP':
            save_opts.update(quality=quality, method=5)
        else:
            save_opts.update(optimize=True, compress_level=9)
        if keep_metadata:
            if original_icc:
                save_opts['icc_profile'] = original_icc
            if exif:
                save_opts['exif'] = exif
        stream = BytesIO()
        converted.save(stream, format=fmt, **save_opts)
        return stream.getvalue()
    finally:
        converted.close()


def _visual_psnr(original: Image.Image, encoded: bytes) -> float:
    """Approximate fidelity score, scaled to max 512 px to bound memory use.

    The alpha channel is included when present. PSNR is a heuristic, not a
    guarantee of indistinguishable appearance or scientifically measured SSIM.
    """
    with Image.open(BytesIO(encoded)) as decoded:
        decoded.load()
        target = decoded.convert('RGBA' if _has_alpha(original) else 'RGB')
    reference = original.convert('RGBA' if _has_alpha(original) else 'RGB')
    reference.thumbnail((512, 512), Image.Resampling.LANCZOS)
    target = target.resize(reference.size, Image.Resampling.LANCZOS)
    try:
        difference = ImageChops.difference(reference, target)
        squared = sum(ImageStat.Stat(difference).sum2)
        mse = squared / max(1, reference.width * reference.height * len(reference.getbands()))
        return 100.0 if mse < 1e-9 else 10 * math.log10(255 * 255 / mse)
    finally:
        reference.close()
        target.close()


def _smart_choice(image: Image.Image, src_fmt: str, options: Options,
                  icc: bytes | None, exif: bytes | None) -> tuple[str, bytes]:
    formats = ([src_fmt] if options.output_format == 'Original' else
               ['PNG', 'WEBP'] if _has_alpha(image) else ['JPEG', 'WEBP', 'PNG']) if options.output_format in ('Auto', 'Original') else [options.output_format]
    # Auto never flattens transparency to JPEG; manual JPEG uses white matte.
    min_psnr = {'Smaller File': 29.0, 'Balanced': 33.0, 'Higher Quality': 38.0}[options.smart_preset]
    # Larger selected quality also increases the minimum fidelity target slightly.
    min_psnr += max(-3.0, min(3.0, (options.quality - 75) / 10.0))
    # Higher Quality tests an extra high-quality encoding.
    qvalues = [options.quality, max(25, options.quality - 12)]
    if options.smart_preset == 'Smaller File':
        qvalues.append(max(20, options.quality - 23))
    if options.smart_preset == 'Higher Quality':
        qvalues.append(min(100, options.quality + 12))
    qvalues = list(dict.fromkeys(qvalues))
    candidates: list[tuple[str, bytes, float]] = []
    for fmt in formats:
        qualities = [options.quality] if fmt == 'PNG' else qvalues
        for q in qualities:
            data = _encoded(image, fmt, q, options.keep_metadata, icc, exif)
            # PNG is lossless; decoding/PSNR is unnecessary.
            score = 100.0 if fmt == 'PNG' else _visual_psnr(image, data)
            candidates.append((fmt, data, score))
    acceptable = [c for c in candidates if c[2] >= min_psnr]
    if acceptable:
        fmt, payload, _ = min(acceptable, key=lambda x: len(x[1]))
    else:
        # Not silently below target: use the highest-fidelity evaluated candidate.
        fmt, payload, _ = max(candidates, key=lambda x: (x[2], -len(x[1])))
    return fmt, payload


def resize_dimensions(source_size: tuple[int, int], options: Options) -> tuple[int, int]:
    """Return output dimensions; locked-pixel mode fits within a bounding box.

    This is intentionally a pure function so users can preview the same values
    the encoder receives, including during batch operations with mixed ratios.
    """
    if not options.resize_enabled:
        return source_size
    options.validate()
    sw, sh = source_size
    if sw < 1 or sh < 1:
        raise ValueError('The source image has invalid dimensions.')
    if options.resize_mode == 'Percent':
        factor = options.resize_percent / 100.0
        if not options.resize_allow_upscale:
            factor = min(factor, 1.0)
        width, height = max(1, round(sw * factor)), max(1, round(sh * factor))
    elif options.resize_lock_aspect:
        factors = []
        if options.resize_width is not None:
            factors.append(options.resize_width / sw)
        if options.resize_height is not None:
            factors.append(options.resize_height / sh)
        factor = min(factors)
        if not options.resize_allow_upscale:
            factor = min(factor, 1.0)
        width, height = max(1, round(sw * factor)), max(1, round(sh * factor))
        if options.resize_width is not None:
            width = min(width, options.resize_width)
        if options.resize_height is not None:
            height = min(height, options.resize_height)
    else:
        width, height = options.resize_width, options.resize_height
        if not options.resize_allow_upscale:
            width, height = min(width, sw), min(height, sh)
    if width > MAX_RESIZE_DIMENSION or height > MAX_RESIZE_DIMENSION or width * height > MAX_RESIZE_PIXELS:
        raise ValueError('Requested image dimensions are too large. Maximum 30,000 px per side and 100 MP.')
    return width, height


def _updated_exif(image: Image.Image, size: tuple[int,int], enabled: bool) -> bytes | None:
    """Preserve requested metadata without leaving stale orientation/dimensions."""
    if not enabled:
        return None
    exif = image.getexif()
    if not exif:
        return None
    exif[274] = 1  # transposed pixels are already upright
    for key, value in ((256, size[0]), (257, size[1]),
                       (40962, size[0]), (40963, size[1])):
        if key in exif:
            exif[key] = value
    return exif.tobytes()


def optimize_image(source: str | Path, options: Options) -> Result:
    """Optimize one image atomically; source and previous outputs are preserved."""
    options.validate()
    src = Path(source).expanduser().resolve(strict=True)
    if not src.is_file() or src.suffix.lower() not in ACCEPTED_EXTENSIONS:
        raise ValueError('Supported files are JPG, JPEG, PNG, and WEBP.')
    if src.stat().st_size == 0:
        raise ValueError('The selected image is empty.')

    out_dir = Path(options.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir = out_dir.resolve()
    start = time.monotonic()
    file_size = src.stat().st_size

    with Image.open(src) as raw:
        source_fmt = _source_format(raw)
        raw.load()  # Corrupt image errors must not yield partial outputs.
        icc = raw.info.get('icc_profile')
        oriented = ImageOps.exif_transpose(raw)
        source_width, source_height = oriented.size
        resized = None
        try:
            target_width, target_height = resize_dimensions(oriented.size, options)
            if (target_width, target_height) != oriented.size:
                resized = oriented.resize((target_width, target_height), Image.Resampling.LANCZOS)
            working = resized if resized is not None else oriented
            exif = _updated_exif(oriented, working.size, options.keep_metadata)
            if options.smart or options.output_format == 'Auto':
                fmt, data = _smart_choice(working, source_fmt, options, icc, exif)
            else:
                fmt = source_fmt if options.output_format == 'Original' else options.output_format
                data = _encoded(working, fmt, options.quality, options.keep_metadata, icc, exif)
        finally:
            if resized is not None:
                resized.close()
            if oriented is not raw:
                oriented.close()

    suffix = options.filename_suffix or '_optimized'
    dest = _destination(out_dir / src.stem, suffix, EXTENSIONS[fmt])
    handle, temp_path = tempfile.mkstemp(prefix='.imageflow-', suffix=EXTENSIONS[fmt], dir=str(out_dir))
    try:
        with os.fdopen(handle, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        with Image.open(temp_path) as check:
            check.verify()
        # Avoid overwriting a previously saved output.
        while dest.exists():
            dest = _destination(out_dir / src.stem, suffix, EXTENSIONS[fmt])
        os.replace(temp_path, dest)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    return Result(str(src), str(dest), file_size, dest.stat().st_size,
                  time.monotonic() - start, fmt, source_width, source_height,
                  target_width, target_height)
