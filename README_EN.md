> **SOURCE REVIEW PACKAGE — NOT PUBLISHED.** Source files use `GPL-3.0-only`.
> This copy uses a generated review-only icon because the redistribution rights for the approved logo
> and application screenshots have not yet been cleared. See `COPYRIGHT.md`, `RELEASE_BLOCKERS.md`,
> `THIRD_PARTY_NOTICES.md` and `LICENSE` before any public release. The original official artwork
> remains in the prior private project archive, not in this review copy.

# SoftRyva ImageFlow V0.3.1 — Image Resizer + Branded Setup Builder

A free, locally running Windows desktop app for converting, optimizing and now resizing images. **This is the full source + Setup builder, not a precompiled Windows installer.** Use `BUILD_SETUP_WINDOWS.bat` on Windows with Python and Inno Setup 6.6+ to generate an installer. All V0.3.0 functionality is retained.

## New in V0.3.0 — Image Resizer

Open **IMAGE RESIZER** near the Optimization Level controls (or its feature card, or Settings → Configure Resizer). Turn on resizing, then choose:

- **Pixels:** Set Width, Height or both. With **Keep original aspect ratio** checked (the default), a single value automatically determines the other dimension. Supplying both values scales each image to fit *within* the requested bounding box without stretching. Turn off the lock to force exact width and height (which can stretch an image).
- **Percent:** E.g., `50` to resize to half the width and height, or `25` to one-quarter. Percent mode always preserves the aspect ratio.
- **Allow enlarging smaller images:** Disabled by default. If turned off, dimensions will never exceed the original image's size. Enlargement cannot create missing details.

Click **APPLY RESIZE** to save the configuration, add JPG/PNG/WebP photos, and press **OPTIMIZE IMAGES**. The resizer runs **before** compression/conversion, including in Batch Convert. Every photo retains its own original proportions when the lock is on. The live preview shows expected dimensions for the currently selected image. On completion, the popup shows the old and new dimensions (when they differ), plus **OPEN FOLDER** / **SAVE AS…** actions.

**Example:** A 3840 × 2160 photo resized by 50% becomes 1920 × 1080. With a locked 1000 × 1000 pixel bounding box, it becomes 1000 × 562 pixels (rounding to nearest pixel). Transparency is maintained in PNG and suitably encoded WebP. Selecting JPEG explicitly turns transparent pixels white, as in V0.2.

## Run on Windows

1. Install Python 3.10+ from https://www.python.org/downloads/windows/ with **Add Python to PATH** enabled.
2. Extract this ZIP into a **new folder**. Do not overwrite a running V0.2.0 application.
3. Double-click `START_WINDOWS.bat`. Internet is required to download dependencies during first setup; subsequent image operations work fully offline.
4. Find `IMAGE RESIZER` above the Optimize button in the scrollable right-hand pane. You can also open Settings → Image Resizer.
5. Add one or more images, click Optimize, and use **OPEN FOLDER** to find results. The default is `Pictures\ImageFlow\Output`.

V0.2.0 local settings and history use the **same** local data directory, so they remain available when V0.3.0 starts. Resize is **off by default** to avoid changing existing workflows. All input photos and previously generated outputs are preserved.

## Existing features maintained

- Smart Compression (multiple real encoder candidates, approximate visual-fidelity testing; **not AI**).
- Original / Auto / JPEG / PNG / WebP selection; Auto keeps alpha transparency.
- Batch Convert, directory loading, drag and drop when optional tkinterdnd2 is installed.
- Real before/after image preview, History, Dashboard, output-folder selection.
- Completion popup, **Open Results** and **Save As**, metadata privacy settings, safe collision-proof output naming, responsive scrollable controls.

## Test or build

Run tests from the extracted folder with `python -m unittest discover -s tests -v`. On Windows run `BUILD_WINDOWS_EXE.bat` to build `dist\SoftRyva-ImageFlow.exe`. The executable was **not compiled/tested on Windows in this environment**. Thoroughly test on your own Windows PC before creating an installer or publishing the software.

## Important notes

- PNG compression is lossless in pixel values when not resized; resizing **necessarily changes pixels**, even if output format is PNG. JPEG/WebP compression usually incurs visual losses.
- EXIF orientation is normalized before resize; optional metadata dimensions are updated where tags exist. Retention of all metadata fields is not guaranteed across formats.
- Upscaling does not invent detail; percentage and pixel sizes are capped to avoid extreme outputs. Manual JPEG conversion flattens transparency on white.
- No cloud upload, accounts, AI model, GPU encoder, built-in software updates or analytics are implemented. Source is licensed GPL-3.0-only; see LICENSE. Trademark/artwork clearance is pending.

## Project structure

- `core.py` — image resizing/optimization/conversion engine.
- `imageflow.py` — Tkinter desktop UI, Resizer editor, Batch Convert, History, Settings.
- `assets/` — GPL-licensed temporary generated icons for source review; not the approved product logo.
- `tests/` — existing V0.2.0 regressions plus Resizer tests.
- `docs/actual_v03_resize_dialog.png` — screenshot from a headless GUI test.
- `START_WINDOWS.bat` and `BUILD_WINDOWS_EXE.bat` — local Windows scripts.


## V0.3.1 — Easier scrolling + unified SoftRyva installer

- The vertical scrollbars are now at least **24px wide** and scale up on high-DPI displays, including Optimize, Settings, Image Resizer and History. The scroll thumb is blue for easier mouse use.
- `BUILD_SETUP_WINDOWS.bat` runs 26 tests, generates brand artwork, bundles a standalone EXE using PyInstaller, compiles the Inno Setup installer, and creates a SHA-256 hash.
- The installer has shared **SoftRyva** branding with program-specific **ImageFlow** icon and product name. Dark wizard, welcome banner, per-user installation (no admin), optional Desktop shortcut, Start Menu entry and uninstall support.
- The installer deliberately **does not delete** local settings, history, input photos or saved outputs when uninstalling.
- The generated installer (on Windows) is `dist_setup\SoftRyva_ImageFlow_Setup_v0.3.1.exe`. Python is not needed to **run the installed program**.
- Dependencies must be downloaded for the build once; running the installed app is offline. A Windows installer has **not** been compiled or run in the current Linux environment; test it on Windows before publication.
- `installer/shared/SoftRyva_Installer_Common.iss` is the reusable publisher template. For future products, change their product `.iss` file, icon and `installer/product.json` branding config; each program must have a **different and stable AppId**.
