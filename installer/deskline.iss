; Deskline Inno Setup script — Tauri shell + PyInstaller backend
#define MyAppName "Deskline"
#define MyAppVersion "0.5.13"
#define MyAppPublisher "AndalusGames"
#define MyAppURL "https://github.com/AndalusGames"
#define MyAppExeName "deskline-desktop.exe"

[Setup]
AppId={{8F3C2A91-6D4E-4B17-9C2A-DESKLINE0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=DesklineSetup-{#MyAppVersion}
SetupIconFile=..\assets\deskline.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
InfoBeforeFile=
LicenseFile=

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; PyInstaller backend (Deskline.exe) + staged Tauri shell (deskline-desktop.exe)
Source: "..\dist\Deskline\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Deskline\screenshots"
; Keep DB by default — user data. Uncomment next line to wipe DB on uninstall:
; Type: files; Name: "{localappdata}\Deskline\deskline.db"
