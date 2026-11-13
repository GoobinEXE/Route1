; Inno Setup 6 — instalador Route Pico (Windows x64)
; Compilar: ISCC /DMyAppVersion=1.0.0 packaging/windows/RoutePico.iss
; Pré-requisito: dist\RoutePico\ gerado pelo PyInstaller.

#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif

#define MyAppName "Route Pico"
#define MyAppExeName "RoutePico.exe"
#define MyAppPublisher "Dark Room"
#define MyAppURL "https://github.com/GoobinEXE/Route1"

[Setup]
; AppId mantido de Route 1 Kit: o instalador atualiza a instalação existente.
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
OutputBaseFilename=Route-Pico-{#MyAppVersion}-windows-x64-setup
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

[InstallDelete]
; Executável e atalhos com o nome antigo (Route 1 Kit <= 1.1.x).
Type: files; Name: "{app}\Route1Kit.exe"
Type: files; Name: "{group}\Route 1 Kit.lnk"
Type: files; Name: "{autodesktop}\Route 1 Kit.lnk"

[Files]
Source: "..\..\dist\RoutePico\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
