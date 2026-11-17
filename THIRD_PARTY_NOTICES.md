# Third-party licenses and attribution (pre-release inventory)

This source tree contains original ImageFlow sources and no vendored third-party Python
libraries. Runtime/build dependencies are installed separately. At packaging time, the
Windows executable may include third-party Python, Tcl/Tk, Pillow and TkDnD components;
**their actual installed licenses and notices must be captured from the exact build**
prior to any public binary release. This file is an inventory, not a complete legal audit.

| Component | Role | License shown by upstream | Primary source | Status |
|---|---|---|---|---|
| Pillow | JPEG/PNG/WebP image processing | MIT-CMU | https://github.com/python-pillow/Pillow/blob/main/LICENSE | Include the exact license notice from the distributed version |
| tkinterdnd2 | Optional drag-and-drop wrapper and bundled tkdnd | MIT for the PyPI wrapper; bundled tkdnd rights/notice need separate verification | https://pypi.org/project/tkinterdnd2/ and https://github.com/petasis/tkdnd | Review binary components before public distribution |
| Python / Tcl / Tk | Interpreter and GUI toolkit | Their respective OSI-compatible licenses | https://docs.python.org/3/license.html | Verify and supply notices from the build |
| PyInstaller | Build tool, not original application code | GPL with executable-bundling exception | https://pyinstaller.org/en/stable/license.html | Preserve notices if bundled files require them |
| Inno Setup | Windows Setup compiler | Project-specific license | https://jrsoftware.org/isinfo.php | Do not claim Inno sources are covered by GPL-3.0-only |

## Not yet approved for redistribution

- The pre-existing SoftRyva / ImageFlow logos and screenshots in the prior builder ZIP.
- Any unpublished font/image assets for which redistributable rights have not been documented.

## Important

ImageFlow's own source code uses `GPL-3.0-only`. Upstream libraries do **not** thereby
become GPL-licensed; they remain under their stated licenses and copyright notices.
The installer must ship `LICENSE` and notices. Before SignPath application, confirm that
**all software components shipped in signed binaries** meet SignPath Foundation's terms.
