# SoftRyva ImageFlow

**Free and open-source image optimization, conversion, and resizing for Windows.**

**Version:** 0.3.1  
**License:** GNU General Public License v3.0 (GPL-3.0)  
**Platform:** Windows  
**Status:** Public open-source project; code signing application in preparation (not yet signed by SignPath Foundation).

SoftRyva ImageFlow is a desktop utility designed to make everyday image tasks easier from a clear, accessible interface. Image processing is performed locally on the user's computer.

## Features

- **Image compression:** reduce image file sizes with configurable output quality.
- **Format conversion:** work with JPEG, PNG, and WebP image formats.
- **Image resizing:** change image dimensions with aspect-ratio controls.
- **Batch processing:** apply operations to multiple images.
- **Before-and-after preview:** review the result before saving.
- **Original file protection:** produce new output files without overwriting original images in the normal workflow.

The available features may differ slightly between development builds and released installers. Check the release notes for the version you download.

## Download

Windows releases and downloadable installation files are distributed through the SoftRyva release repository:

- [SoftRyva official GitHub Releases](https://github.com/easam028-debug/softryva-releases/releases)
- [ImageFlow v0.3.1 installer](https://github.com/easam028-debug/softryva-releases/releases/download/v0.3.1/SoftRyva_ImageFlow_Setup_v0.3.1.exe)

**Security notice:** The public installer may currently be unsigned. Do not bypass operating-system security warnings without independently verifying the software and its source. Only download files from the official release links above.

## Build from source

The source code, dependencies, and Windows build scripts are stored in this repository.

1. Review `requirements.txt` and the license and third-party notices.
2. On Windows, use `START_WINDOWS.bat` for the source-based launch workflow, following its prompts.
3. Use `BUILD_WINDOWS_EXE.bat` or `BUILD_SETUP_WINDOWS.bat` for local build workflows.
4. Refer to `.github/workflows/` for the GitHub Actions build configuration and to `tests/` for automated tests.

Build prerequisites, network requirements, and generated artifact locations depend on the scripts and environment. Read the scripts before execution; a successful build must be tested before public distribution.

## Privacy

**This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.**

Image processing is intended to take place locally. The application does not require an account for its regular image-processing workflow. Network access may be used when the user separately visits GitHub, the project website, or other external download/update pages. Review [third-party notices](THIRD_PARTY_NOTICES.md) for information about bundled dependencies.

## Code signing policy

**Code signing status:** SignPath Foundation code signing has **not yet been approved or enabled** for this project.

**Intended signing provider (subject to approval):** Free code signing provided by SignPath.io, certificate by SignPath Foundation.

**Source of truth:** The public [SoftRyva-ImageFlow repository](https://github.com/easam028-debug/SoftRyva-ImageFlow), including its history, build scripts, and GitHub Actions configuration.

**Team roles for release governance:**

- **Committer / maintainer:** [@easam028-debug](https://github.com/easam028-debug), responsible for project source code and controlled changes.
- **Reviewer:** [@easam028-debug](https://github.com/easam028-debug), responsible for reviewing external contributions before they are merged. Changes must not be merged without authorized review.
- **Signing approver:** [@easam028-debug](https://github.com/easam028-debug), responsible for reviewing and explicitly approving each signing request after a release is verified.

All maintainers and individuals with repository or signing access are required to enable multi-factor authentication. Signed release candidates, when signing becomes available, must be traceable to the public repository and verifiably produced through the approved build process. Each signing request requires explicit approval; no arbitrary external or prebuilt files may be signed under this project.

The project will not claim SignPath Foundation endorsement, approval, or an active signature unless and until the application is accepted and a corresponding binary is signed.

For applicable conditions, see the [SignPath Foundation terms](https://signpath.org/terms.html).

## Security and reporting

Please review [SECURITY.md](SECURITY.md) before reporting a vulnerability. Avoid disclosing security-sensitive details in public issue reports.

## Contributing

Contributions are welcome through GitHub issues and pull requests. Proposed changes will be reviewed before merging, with particular care for build scripts, release configuration, and dependency changes.

## License

SoftRyva ImageFlow is licensed under the **GNU GPL v3.0**. See [LICENSE](LICENSE) or the repository's GPL-3.0 license section. Third-party components may have separate license obligations; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

**SoftRyva — useful Windows tools, developed with transparency and respect for users.**
