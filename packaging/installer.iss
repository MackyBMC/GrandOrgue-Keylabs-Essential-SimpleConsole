; Inno Setup 6 script: wraps dist\keylab_go_bridge.dist (Nuitka standalone). Build through packaging\build_windows.ps1.
; Installs read-only program files only; config, takes and window layout live in %APPDATA%\KeyLabGrandOrgue and survive uninstall / upgrade.
#define AppName "KeyLab GrandOrgue Bridge"
#ifndef AppVersion
  #error "Pass AppVersion from version.py via packaging\build_windows.ps1."
#endif
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
var
  ModePage: TInputOptionWizardPage;
  DirSet: Boolean;

function IsPortable: Boolean;
begin
  Result := ModePage.SelectedValueIndex = 1;
end;

var
  GOPage: TInputDirWizardPage;

function GOFolder(Param: String): String;
begin
  if GOPage <> nil then Result := GOPage.Values[0]
  else Result := ExpandConstant('{userdocs}\GrandOrgue');
end;

function DataDir: String;
begin
  if IsPortable then Result := ExpandConstant('{app}')
  else Result := ExpandConstant('{userappdata}\KeyLabGrandOrgue');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ForceDirectories(DataDir);
    SaveStringToFile(DataDir + '\go_folder.txt', GOFolder('') + #13#10, False);
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (GOPage <> nil) and (CurPageID = GOPage.ID) then
    if not DirExists(GOPage.Values[0]) then
      Result := MsgBox('That folder does not exist yet. Use it anyway?', mbConfirmation, MB_YESNO) = IDYES
    else if not (DirExists(GOPage.Values[0] + '\Organs') or DirExists(GOPage.Values[0] + '\Settings')) then
      Result := MsgBox('This folder has no Organs or Settings sub-folder, so it does not look like your GrandOrgue folder. Use it anyway?', mbConfirmation, MB_YESNO) = IDYES;
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
procedure InitializeWizard;
begin
  ModePage := CreateInputOptionPage(wpWelcome, 'Installation type', 'How do you want to install?',
    'Choose Standard for a normal install, or Portable to keep the program and all settings together in one folder (USB stick, test copy).',
    True, False);
  ModePage.Add('Standard - program files separate, settings in %APPDATA%\KeyLabGrandOrgue');
  ModePage.Add('Portable - program and settings together in the folder you choose next');
  ModePage.SelectedValueIndex := 0;
  GOPage := CreateInputDirPage(ModePage.ID, 'GrandOrgue folder', 'Where is your GrandOrgue user folder?',
    'This is the folder that holds your Organs, Settings and Combinations (the default is Documents\GrandOrgue; choose another if you moved it).', False, '');
  GOPage.Add('');
  GOPage.Values[0] := ExpandConstant('{userdocs}\GrandOrgue');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpSelectDir) and IsPortable and not DirSet then
  begin
    WizardForm.DirEdit.Text := ExpandConstant('{userdocs}\KeyLabGrandOrgueBridge-Portable');
    DirSet := True;
  end;
end;
