; Inno Setup 6 Script for Elect Twin 0.3.0 (x64)
; Produces: Elect-Twin-Setup-0.3.0-x64.exe

#define MyAppName "Elect Twin"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "Electri"
#define MyAppURL "https://github.com/electri-ai/elect-twin"
#define MyAppExeName "ElectTwin.exe"

[Setup]
AppId={{5E2B9611-B645-4DC3-81D8-6878CE4D2026}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\elect-twin-mac\LICENSE
OutputDir=dist
OutputBaseFilename=Elect-Twin-Setup-0.3.0-x64
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main C# WebView2 Executable & Dependencies
Source: "ElectTwinWin\bin\Release\net8.0-windows\win-x64\publish\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

; Standalone Engine Runtimes
Source: "dist\twin-server.exe"; DestDir: "{app}\Runtime"; Flags: ignoreversion
Source: "dist\rooms-server.exe"; DestDir: "{app}\Rooms"; Flags: ignoreversion

; Documentation
Source: "..\elect-twin-mac\LICENSE"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\elect-twin-mac\README.md"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\elect-twin-mac\docs\INSTALL.md"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\elect-twin-mac\docs\SUPPORT-MATRIX.md"; DestDir: "{app}\Docs"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Register custom URI protocol handler: elect-twin://
Root: HKCU; Subkey: "Software\Classes\elect-twin"; ValueType: string; ValueName: ""; ValueData: "URL:Elect Twin Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\elect-twin"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\elect-twin\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\elect-twin\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Helper function to verify Microsoft Edge WebView2 runtime availability
function IsWebView2Installed(): Boolean;
var
  InstalledVersion: String;
begin
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', InstalledVersion) or
            RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', InstalledVersion);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsWebView2Installed() then
  begin
    if MsgBox('Microsoft Edge WebView2 Runtime is required to run Elect Twin.' + #13#10#13#10 +
              'Would you like to continue the setup anyway? (You can install WebView2 later from Microsoft)',
              mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := False;
    end;
  end;
end;
