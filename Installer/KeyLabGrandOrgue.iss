#define MyAppName "GrandOrgue KeyLab Console"
#define MyAppVersion "2026.09.24"
#define MyAppPublisher "GrandOrgue KeyLab Console"
#define MyAppExeName "keylab_go_bridge.exe"

[Setup]
AppId={{B9B6636D-1D9D-4B80-9DF5-9D8BCB8E4A26}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\GrandOrgue KeyLab Console
DefaultGroupName={#MyAppName}
OutputDir=..\release
OutputBaseFilename=GrandOrgue-KeyLab-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
Uninstallable=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut for GrandOrgue + KeyLab Console"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Files]
Source: "{#SourcePath}\..\Scripts\build\{#MyAppExeName}"; DestDir: "{app}\Scripts\build"; Flags: ignoreversion
Source: "{#SourcePath}\..\Scripts\config.yaml"; DestDir: "{app}\Scripts"; Flags: ignoreversion
Source: "{#SourcePath}\..\Scripts\start_keylab_bridge.bat"; DestDir: "{app}\Scripts"; Flags: ignoreversion
Source: "{#SourcePath}\..\Scripts\start_keylab_bridge.ps1"; DestDir: "{app}\Scripts"; Flags: ignoreversion
Source: "{#SourcePath}\..\Scripts\start_keylab_grandorgue.bat"; DestDir: "{app}\Scripts"; Flags: ignoreversion
Source: "{#SourcePath}\..\Scripts\start_keylab_grandorgue.ps1"; DestDir: "{app}\Scripts"; Flags: ignoreversion
Source: "{#SourcePath}\..\Scripts\setup_keylab_bridge.bat"; DestDir: "{app}\Scripts"; Flags: ignoreversion
Source: "{#SourcePath}\..\Scripts\setup_keylab_bridge.ps1"; DestDir: "{app}\Scripts"; Flags: ignoreversion
Source: "{#SourcePath}\..\Settings\Friesach-midi-settings-KeyLab.yaml"; DestDir: "{app}\Settings"; Flags: ignoreversion
Source: "{#SourcePath}\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}\..\KeyLab_GrandOrgue_HardwareSettings.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\GrandOrgue KeyLab Console"; Filename: "{app}\Scripts\start_keylab_grandorgue.bat"; WorkingDir: "{app}\Scripts"; IconFilename: "{app}\Scripts\build\{#MyAppExeName}"
Name: "{group}\KeyLab Bridge"; Filename: "{app}\Scripts\start_keylab_bridge.bat"; WorkingDir: "{app}\Scripts"; IconFilename: "{app}\Scripts\build\{#MyAppExeName}"
Name: "{autodesktop}\GrandOrgue + KeyLab Console"; Filename: "{app}\Scripts\start_keylab_grandorgue.bat"; WorkingDir: "{app}\Scripts"; IconFilename: "{app}\Scripts\build\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\Scripts\start_keylab_grandorgue.bat"; Description: "Start GrandOrgue KeyLab Console now"; Flags: postinstall skipifsilent