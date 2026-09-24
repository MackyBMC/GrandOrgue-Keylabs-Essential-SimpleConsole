#define MyAppName "GrandOrgue KeyLab Console"
#define MyAppVersion "2026.09.24"
#define MyAppPublisher "GrandOrgue KeyLab Console"
#define MyAppExeName "keylab_go_bridge.exe"

[Setup]
AppId={{B9B6636D-1D9D-4B80-9DF5-9D8BCB8E4A26}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={code:GetGrandOrgueWorkspace}
DisableDirPage=yes
DefaultGroupName={#MyAppName}
OutputDir=..\release
OutputBaseFilename=GrandOrgue-KeyLab-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
Uninstallable=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut for GrandOrgue + KeyLab Console"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Files]
Source: "{#SourcePath}\..\Scripts\build\{#MyAppExeName}"; DestDir: "{app}\Scripts\build"; Flags: ignoreversion uninsneveruninstall
Source: "{#SourcePath}\..\Scripts\config.yaml"; DestDir: "{app}\Scripts"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall
Source: "{#SourcePath}\..\Scripts\start_keylab_bridge.bat"; DestDir: "{app}\Scripts"; Flags: ignoreversion uninsneveruninstall
Source: "{#SourcePath}\..\Scripts\start_keylab_bridge.ps1"; DestDir: "{app}\Scripts"; Flags: ignoreversion uninsneveruninstall
Source: "{#SourcePath}\..\Scripts\start_keylab_grandorgue.bat"; DestDir: "{app}\Scripts"; Flags: ignoreversion uninsneveruninstall
Source: "{#SourcePath}\..\Scripts\start_keylab_grandorgue.ps1"; DestDir: "{app}\Scripts"; Flags: ignoreversion uninsneveruninstall
Source: "{#SourcePath}\..\Scripts\setup_keylab_bridge.bat"; DestDir: "{app}\Scripts"; Flags: ignoreversion uninsneveruninstall
Source: "{#SourcePath}\..\Scripts\setup_keylab_bridge.ps1"; DestDir: "{app}\Scripts"; Flags: ignoreversion uninsneveruninstall
Source: "{#SourcePath}\..\Settings\Friesach-midi-settings-KeyLab.yaml"; DestDir: "{app}\Settings"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall
Source: "{#SourcePath}\..\README.md"; DestDir: "{app}"; Flags: ignoreversion uninsneveruninstall
Source: "{#SourcePath}\..\KeyLab_GrandOrgue_HardwareSettings.md"; DestDir: "{app}"; Flags: ignoreversion uninsneveruninstall

[Dirs]
Name: "{app}\Scripts\build"
Name: "{app}\Settings"
Name: "{app}\Organs"
Name: "{app}\Combinations"
Name: "{app}\Audio recordings"
Name: "{app}\MIDI recordings"

[Icons]
Name: "{group}\GrandOrgue KeyLab Console"; Filename: "{app}\Scripts\start_keylab_grandorgue.bat"; WorkingDir: "{app}\Scripts"; IconFilename: "{app}\Scripts\build\{#MyAppExeName}"
Name: "{group}\KeyLab Bridge"; Filename: "{app}\Scripts\start_keylab_bridge.bat"; WorkingDir: "{app}\Scripts"; IconFilename: "{app}\Scripts\build\{#MyAppExeName}"
Name: "{autodesktop}\GrandOrgue + KeyLab Console"; Filename: "{app}\Scripts\start_keylab_grandorgue.bat"; WorkingDir: "{app}\Scripts"; IconFilename: "{app}\Scripts\build\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\Scripts\start_keylab_grandorgue.bat"; Description: "Start GrandOrgue KeyLab Console now"; Flags: postinstall skipifsilent

[Code]
function GetGrandOrgueWorkspace(Param: String): String;
begin
	Result := ExpandConstant('{userdocs}\GrandOrgue');
end;

function GrandOrgueExecutableExists(): Boolean;
var
	Candidates: array[0..4] of String;
	I: Integer;
begin
	Candidates[0] := ExpandConstant('{autopf}\GrandOrgue\bin\GrandOrgue.exe');
	Candidates[1] := ExpandConstant('{autopf}\GrandOrgue\GrandOrgue.exe');
	Candidates[2] := ExpandConstant('{autopf32}\GrandOrgue\bin\GrandOrgue.exe');
	Candidates[3] := ExpandConstant('{autopf32}\GrandOrgue\GrandOrgue.exe');
	Candidates[4] := ExpandConstant('{userdocs}\GrandOrgue\GrandOrgue.exe');
	Result := False;
	for I := 0 to 4 do
	begin
		if FileExists(Candidates[I]) then
		begin
			Result := True;
			Exit;
		end;
	end;
end;

function InitializeSetup(): Boolean;
begin
	Result := GrandOrgueExecutableExists();
	if not Result then
	begin
		MsgBox(
			'GrandOrgue was not found.' + #13#10#13#10 +
			'Install GrandOrgue first, then run this setup again.' + #13#10 +
			'The console uses GrandOrgue''s existing user folders in Documents.',
			mbError, MB_OK);
	end;
end;