; Inno Setup 6 - compile this script after PyInstaller has produced ..\dist\RawView\
; Download: https://jrsoftware.org/isdl.php
;
; Upgrades: AppId must stay fixed across releases. Re-running this installer updates
; an existing per-user install in place (same folder, files replaced). New installs
; behave as a normal first-time wizard (no prior AppId in the registry).
#define MyAppName "RawView"
#define MyAppVersion "0.1.0"
#define MyAppVersionInfo "0.1.0.0"
#define MyAppPublisher "RawView"
#define MyAppURL "https://github.com"
#define MyAppExeName "RawView.exe"

[Setup]
AppId={{A7E8F3B2-4C1D-5E6F-8091-2A3B4C5D6E7F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersionInfo}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
; Hide destination page only when a previous install is found (update path).
DisableDirPage=auto
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist_installer
OutputBaseFilename=RawView-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\RawView\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
