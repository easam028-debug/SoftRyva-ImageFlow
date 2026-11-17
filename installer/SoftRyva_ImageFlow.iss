; SPDX-License-Identifier: GPL-3.0-only
; Copyright (C) 2026 SoftRyva Development contributors

; ImageFlow-specific values. For each future SoftRyva product,
; create a new product .iss with its OWN AppId and executable/icon.
; Reuse shared/SoftRyva_Installer_Common.iss unchanged.
#define BrandName "SoftRyva"
#define ProductName "ImageFlow"
#define FullName "SoftRyva ImageFlow"
#define ProductVersion "0.3.1"
; Keep this GUID unchanged for future ImageFlow versions; unique for each program.
#define ProductAppId "{{B905C670-8328-5456-9596-FBC89FCED61F}"
#define ProductExe "SoftRyva-ImageFlow.exe"
#define ProductExePath "..\dist\SoftRyva-ImageFlow.exe"
#define ProductIcon "..\assets\ImageFlow.ico"
#define ProductWizardImage "branding\welcome.png"
#define ProductWizardSmall "branding\small.png"
#define ProductInstallerName "SoftRyva_ImageFlow_Setup_v0.3.1"

#include "shared\SoftRyva_Installer_Common.iss"
