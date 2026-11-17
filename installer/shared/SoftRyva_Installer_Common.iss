; SPDX-License-Identifier: GPL-3.0-only
; Copyright (C) 2026 SoftRyva Development contributors

; SoftRyva unified Windows installer template (Inno Setup 6.6+).
; Shared across SoftRyva applications. Product-specific values are
; defined in installer/SoftRyva_ImageFlow.iss (or future per-app file).
[Setup]
AppId={#ProductAppId}
AppName={#FullName}
AppVersion={#ProductVersion}
AppVerName={#FullName} {#ProductVersion}
AppPublisher={#BrandName}
AppComments={#BrandName} original desktop software
UninstallDisplayName={#FullName}
UninstallDisplayIcon={app}\{#ProductExe}
VersionInfoCompany={#BrandName}
VersionInfoDescription={#FullName} Setup
VersionInfoProductName={#FullName}
VersionInfoProductVersion={#ProductVersion}
VersionInfoVersion={#ProductVersion}.0
DefaultDirName={localappdata}\Programs\{#BrandName}\{#ProductName}
DefaultGroupName={#BrandName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
UsePreviousAppDir=yes
UsePreviousTasks=yes
CloseApplications=yes
WizardStyle=modern dark
WizardImageFile={#ProductWizardImage}
WizardSmallImageFile={#ProductWizardSmall}
WizardImageBackColor=#07162A
WizardSmallImageBackColor=#07162A
SetupIconFile={#ProductIcon}
OutputDir=..\dist_setup
OutputBaseFilename={#ProductInstallerName}
Compression=lzma2
SolidCompression=yes
MinVersion=10.0
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#ProductExePath}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\COPYRIGHT.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#FullName}"; Filename: "{app}\{#ProductExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#FullName}"; Filename: "{app}\{#ProductExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ProductExe}"; Description: "Launch {#FullName}"; Flags: nowait postinstall skipifsilent

; Deliberately no [UninstallDelete] for user settings/history/images.
; They are stored outside the installation directory and must be preserved.
