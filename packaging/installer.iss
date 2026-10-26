; Inno Setup 6 script: wraps dist\keylab_go_bridge.dist (Nuitka standalone). Build:  iscc packaging\installer.iss
; Installs read-only program files only; config, takes and window layout live in %APPDATA%\KeyLabGrandOrgue and survive uninstall / upgrade.
#define AppName "KeyLab GrandOrgue Bridge"
#define AppVersion "2.0.0"
#define Exe "KeyLabGrandOrgueBridge.exe"

[Setup]
AppId={{B6F0C1A2-5D7E-4F3A-9C21-7A6E2D4B8F10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=MackyBMC
AppPublisherURL=https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableDirPage=no
OutputDir=..\dist\installer
OutputBaseFilename=KeyLabGrandOrgueBridge-{#AppVersion}-setup
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#Exe}
CloseApplications=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Tasks]
Name: starter; Description: "Copy starter Combinations and MIDI settings into my GrandOrgue folder (never overwrites existing files)"; GroupDescription: "GrandOrgue content:"

[Files]
Source: "..\Combinations\*"; DestDir: "{code:GOFolder}\Combinations"; Tasks: starter; Flags: recursesubdirs onlyifdoesntexist uninsneveruninstall
Source: "..\Settings\*"; DestDir: "{code:GOFolder}\Settings"; Tasks: starter; Flags: recursesubdirs onlyifdoesntexist uninsneveruninstall
Source: "..\dist\keylab_go_bridge.dist\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "portable.flag"; DestDir: "{app}"; Check: IsPortable; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#Exe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#Exe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#Exe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

; user data is deliberately NOT in [UninstallDelete]

[Code]
function GOFolder(Param: String): String;
begin
  Result := ExpandConstant('{userdocs}\GrandOrgue');
end;

function GrandOrgueFound: Boolean;
begin
  Result := FileExists(ExpandConstant('{autopf}\GrandOrgue\bin\GrandOrgue.exe')) or
            FileExists(ExpandConstant('{autopf}\GrandOrgue\GrandOrgue.exe')) or
            FileExists(ExpandConstant('{autopf32}\GrandOrgue\bin\GrandOrgue.exe')) or
            FileExists(ExpandConstant('{autopf32}\GrandOrgue\GrandOrgue.exe')) or
            DirExists(ExpandConstant('{userdocs}\GrandOrgue'));
end;

function LoopMidiFound: Boolean;
begin
  Result := FileExists(ExpandConstant('{autopf32}\Tobias Erichsen\loopMIDI\loopMIDI.exe')) or
            FileExists(ExpandConstant('{autopf}\Tobias Erichsen\loopMIDI\loopMIDI.exe'));
end;

function InitializeSetup: Boolean;
var Msg: String; Err: Integer;
begin
  Result := True;
  if not GrandOrgueFound then
    if MsgBox('GrandOrgue was not found on this computer.' + #13#10 + 'Open the GrandOrgue download page now?' + #13#10 + '(Choose No to continue installing anyway.)', mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://github.com/GrandOrgue/grandorgue/releases', '', '', SW_SHOW, ewNoWait, Err);
  if not LoopMidiFound then
    if MsgBox('loopMIDI was not found (the bridge needs a virtual MIDI port).' + #13#10 + 'Open the loopMIDI download page now?' + #13#10 + '(Choose No to continue installing anyway.)', mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://www.tobias-erichsen.de/software/loopmidi.html', '', '', SW_SHOW, ewNoWait, Err);
end;

{ Wizard page "Installation type": Standard (program files, settings in %APPDATA%) or Portable (everything in one folder you choose). }
var
  ModePage: TInputOptionWizardPage;
  DirSet: Boolean;

function IsPortable: Boolean;
begin
  Result := ModePage.SelectedValueIndex = 1;
end;

procedure InitializeWizard;
begin
  ModePage := CreateInputOptionPage(wpWelcome, 'Installation type', 'How do you want to install?',
    'Choose Standard for a normal install, or Portable to keep the program and all settings together in one folder (USB stick, test copy).',
    True, False);
  ModePage.Add('Standard - program files separate, settings in %APPDATA%\KeyLabGrandOrgue');
  ModePage.Add('Portable - program and settings together in the folder you choose next');
  ModePage.SelectedValueIndex := 0;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpSelectDir) and IsPortable and not DirSet then
  begin
    WizardForm.DirEdit.Text := ExpandConstant('{userdocs}\KeyLabGrandOrgueBridge-Portable');
    DirSet := True;
  end;
end;
