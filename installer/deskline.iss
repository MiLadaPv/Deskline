; Deskline Inno Setup script — produces a normal Windows Setup.exe
#define MyAppName "Deskline"
#define MyAppVersion "0.5.0"
#define MyAppPublisher "AndalusGames"
#define MyAppURL "https://github.com/AndalusGames"
#define MyAppExeName "Deskline.exe"
#define MySupportURL "mailto:milanochka.llc@gmail.com"

[Setup]
AppId={{8F3C2A91-6D4E-4B17-9C2A-DESKLINE0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MySupportURL}
DefaultDirName={autopf}\{#MyAppName}
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
LicenseFile=LICENSE.txt
InfoBeforeFile=

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\Deskline\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Deskline\screenshots"
; Keep DB by default — user data. Uncomment next line to wipe DB on uninstall:
; Type: files; Name: "{localappdata}\Deskline\deskline.db"
