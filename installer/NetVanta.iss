; Inno Setup script - builds NetVanta-Setup-<version>.exe from the PyInstaller output in dist\NetVanta
#define AppName "NetVanta"
#define AppVersion "1.0.0"
#define AppPublisher "Avishka Withanage"

[Setup]
AppId={{6F1D2C54-8B7A-4C1E-9A53-5E7B1A9C0D42}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/Avishkawithanage/NetVanta
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=NetVanta-Setup-{#AppVersion}
SetupIconFile=..\assets\netvanta.ico
UninstallDisplayIcon={app}\NetVanta.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Installs for the current user without admin rights by default; the user can choose "all users" in the wizard.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\NetVanta\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\NetVanta.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\NetVanta.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\NetVanta.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
