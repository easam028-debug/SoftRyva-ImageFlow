# BLOCKERS — do not publish or request SignPath yet

**Approved for public display:** SoftRyva Development (project/team name). This does not resolve legal title to source contributions.

- [ ] Confirm ownership/permission to license all original source contributions; update
      attribution if a different rights-holder identity is appropriate.
- [ ] Confirm official logo/screenshots redistribution terms; restore only licensed assets.
      The current project deliberately uses generated placeholder art.
- [ ] Reconcile bundled tkinterdnd2/tkdnd, Pillow, Python and Tcl/Tk notices for the exact
      Windows binary. `THIRD_PARTY_NOTICES.md` is not a complete dependency notice bundle.
- [ ] Pin runtime and build tool versions, collect dependency hashes, and lock down the
      Windows build runner. Existing `requirements.txt` uses version ranges; this is NOT
      a bit-for-bit reproducible build.
- [ ] Test both `BUILD_WINDOWS_EXE.bat` and `BUILD_SETUP_WINDOWS.bat` on clean Windows;
      run install / upgrade / uninstall smoke tests.
- [ ] Enable private vulnerability reporting, release review, and 2FA for maintainers.
- [ ] Investigate prior SecureAge and Trapmine detections before presenting a new binary
      as independently verified or safe.
- [ ] Publish a source repository with readable history, release notes and a release
      built from the public source before applying to SignPath Foundation.
- [ ] Confirm full SignPath eligibility at https://signpath.org/terms at application time.

This folder has **NOT** been uploaded or published. Do not confuse this candidate with
existing GitHub release v0.3.1, which was assembled independently.
