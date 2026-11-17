# V0.3.1 — Wider Scrollbars & SoftRyva Installer Builder

- Increased mouse-grabbable scrollbars from 13px to at least 24px, DPI-aware; applied across scrolling pages including History.
- Added reusable Inno Setup (6.6+) SoftRyva publisher template with product-specific branding.
- Added matching branded welcome image, small icon and automatic artwork generator.
- Added one-command Windows build script with tests, EXE + Setup build and SHA-256.
- Retained all V0.3.0 core features, data directory and settings compatibility.
- Reminder: Windows EXE and Inno Setup must still be compiled and tested on Windows.

# Changelog

## V0.3.0 — Image Resizer

- Added pixel sizing (width and/or height) with optional aspect-ratio lock; locked width+height fits bounding box.
- Added percentage scaling, no upscaling by default, optional enlargement, and live dimension preview.
- Runs before format conversion/compression; supports mixed-aspect-ratio batches.
- Main screen button, clickable feature card, Settings button and saved preferences.
- Completion shows dimension changes; keeps prior results, files and settings.
- Added automated tests for resize behavior, alpha, orientation and regressions.

## V0.2.0 — usability and real feature controls

- Completed actions: processing-complete dialog, output-folder opener, Save As, change output folder.
- Adapted small-screen layout and scrolling panes in Optimize and Settings.
- Clickable Smart Compression, Multiple Formats, Secure & Private, Fast & Efficient and High Quality cards.
- Smart Compression tests encoder candidates and selects the smallest candidate above an approximate fidelity threshold; three presets.
- Auto format intelligently searches JPG/WebP/PNG candidates and avoids flattening alpha without explicit JPEG selection.
- Corrected comparison statistics after navigation; preserved original inputs and earlier outputs.
- Added regression tests for Auto, transparency, smart PNG losslessness and format validity.
