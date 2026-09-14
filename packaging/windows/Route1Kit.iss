; Inno Setup 6 — instalador Route 1 Kit (Windows x64)
; Compilar: ISCC /DMyAppVersion=1.0.0 packaging/windows/Route1Kit.iss
; Pré-requisito: dist\Route1Kit\ gerado pelo PyInstaller.

#ifndef MyAppVersion
  #define MyAppVersion "1.0.3"
#endif

#define MyAppName "Route 1 Kit"
#define MyAppExeName "Route1Kit.exe"
#define MyAppPublisher "Dark Room"
#define MyAppURL "https://github.com/GoobinEXE/Route1"

[Setup]
AppId={{8F3C2A1B-9D4E-4F6A-B7C8-1E2D3A4B5C6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\release_artifacts
OutputBaseFilename=Route-1-Kit-{#MyAppVersion}-windows-x64-setup
SetupIconFile=..\..\static\assets\app-icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
; Assinatura Authenticode (opcional): passar /Sroute1sign="…" ao ISCC.
; Ver docs/WINDOWS_SIGNING.md. Sem SignTool definido, o instalador sai sem assinar.
#ifdef ROUTE1_SIGN
SignTool=route1sign
SignedUninstaller=yes
#endif

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\Route1Kit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
