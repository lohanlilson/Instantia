; Atualização pequena do Instantia: contém só os arquivos que mudaram desde a versão BaseVersion.
; Gerado pelo build.py (python build.py --base-dir <pasta da versão anterior> --base-versao X.Y.Z).
#define AppName   "Instantia"
#define AppExe    "Instantia.exe"
#define AppGuid   "8CFC6425-FE9E-43F3-B780-04DB19E19F23"
#ifndef AppPublisher
  #define AppPublisher "Lohan Lilson S. Lopes"
#endif

[Setup]
AppId={{{#AppGuid}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
SetupIconFile=..\assets\instantia.ico
WizardSmallImageFile=..\assets\wizard_small.bmp
OutputDir=..\Saida
OutputBaseFilename=Instantia-Atualizacao-{#BaseVersion}-para-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=force
RestartApplications=no
MinVersion=10.0
SetupLogging=yes

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

#include "..\build\patch_remover.iss"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o Instantia agora"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExe}"; Parameters: "--bandeja"; Flags: nowait runasoriginaluser; Check: WizardSilent

#include "codigo.iss"

[Code]
// só aplica sobre a versão exata para a qual foi gerada
function InitializeSetup(): Boolean;
var
  V: String;
begin
  Result := True;
  if not RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{' + '{#AppGuid}' + '}_is1',
                             'DisplayVersion', V) then
    V := '';
  if V <> '{#BaseVersion}' then
  begin
    Log('Atualização pequena recusada: versão instalada "' + V + '", esperada {#BaseVersion}');
    SuppressibleMsgBox('Esta atualização serve só para o Instantia {#BaseVersion}. Baixe o instalador completo em github.com/lohanlilson/Instantia.',
                       mbError, MB_OK, IDOK);
    Result := False;
  end;
end;
