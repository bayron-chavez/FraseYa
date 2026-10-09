; Instalación por usuario: programa y conexión pública; nunca frases ni cuentas.
#ifndef ConfigPublica
  #error Genera el instalador con scripts/crear_instalador.ps1 para validar su conexion publica.
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{590C5A52-240B-4C92-9C2E-D331F44C34DA}
AppName=FraseYa
AppVersion={#AppVersion}
AppPublisher=FraseYa
DefaultDirName={localappdata}\Programs\FraseYa
DefaultGroupName=FraseYa
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=FraseYa-Instalador
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\FraseYa.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
SetupIconFile=..\assets\fraseya.ico

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "{#ConfigPublica}"; DestDir: "{app}\datos"; DestName: "supabase.json"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\dist\FraseYa\FraseYa.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\FraseYa\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\MANUAL_USUARIO.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\GUIA_ADMINISTRADOR.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\ACEPTACION_EQUIPOS.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\VALIDACION.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\INSTALACION.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\FraseYa"; Filename: "{app}\FraseYa.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\FraseYa"; Filename: "{app}\FraseYa.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\FraseYa.exe"; Description: "Abrir FraseYa"; Flags: nowait postinstall skipifsilent

; No hay UninstallDelete: las frases y configuración generadas por el usuario
; en datos se conservan al desinstalar o actualizar.
