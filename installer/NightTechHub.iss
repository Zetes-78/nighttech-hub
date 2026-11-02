; Night Tech Hub installer (Inno Setup 6)
; Built by build.ps1. Per-user install, no admin rights needed.

#define AppName "Night Tech Hub"
#ifndef AppVersion
  #define AppVersion "1.2.0"
#endif
#define AppPublisher "Night Tech Solutions"
#define AppURL "https://nighttech.solutions"
#define AppExe "NightTechHub.exe"

[Setup]
AppId={{49C6422F-32C9-407F-A40B-5FB02D54959F}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={localappdata}\Programs\Night Tech Hub
DefaultGroupName=Night Tech Hub
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=NightTechHub-Setup
SetupIconFile=NightTechHub.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\NightTechHub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "NightTechHub.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Night Tech Hub"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\NightTechHub.ico"
Name: "{group}\Night Tech Hub data folder"; Filename: "{localappdata}\Night Tech Hub\data"
Name: "{group}\Uninstall Night Tech Hub"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Night Tech Hub"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\NightTechHub.ico"; Tasks: desktopicon

[Dirs]
Name: "{localappdata}\Night Tech Hub\data"; Flags: uninsneveruninstall

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start Night Tech Hub now"; Flags: nowait postinstall skipifsilent

[Messages]
FinishedLabel=Night Tech Hub is installed.%n%nYour customers, tickets and settings are saved in your user folder (AppData\Local\Night Tech Hub\data). Uninstalling or updating the program never deletes them. Use the Backup button in Settings to keep a copy somewhere safe.
