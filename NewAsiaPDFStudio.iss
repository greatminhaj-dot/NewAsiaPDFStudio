#define MyAppName "NewAsiaPDFStudio"
#define MyAppVersion "3.2.0"
#define MyAppPublisher "New Asia Group"
#define MyAppExeName "NewAsiaPDFStudio.exe"

[Setup]
AppId={{BDBB2C57-0B68-437E-B1E8-CBE351A50CA0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\NewAsiaPDFStudio
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=NewAsiaPDFStudio_Setup_3.2_Windows_x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\newasia.ico
VersionInfoVersion=3.2.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=NewAsiaPDFStudio PDF Editor
CloseApplications=yes

[Files]
Source: "dist\NewAsiaPDFStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Registers the app in Open With without forcibly replacing the user's PDF default.
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "NewAsiaPDFStudio"; ValueData: "Software\NewAsiaPDFStudio\Capabilities"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\NewAsiaPDFStudio\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "NewAsiaPDFStudio"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\NewAsiaPDFStudio\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Local PDF viewer and editor"
Root: HKCU; Subkey: "Software\NewAsiaPDFStudio\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "NewAsiaPDFStudio.PDF"
Root: HKCU; Subkey: "Software\Classes\NewAsiaPDFStudio.PDF"; ValueType: string; ValueName: ""; ValueData: "PDF Document"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\NewAsiaPDFStudio.PDF\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\NewAsiaPDFStudio.PDF\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
