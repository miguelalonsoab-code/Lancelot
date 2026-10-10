; =============================================================================
;  Instalador de Lancelot (Inno Setup 6)
;
;  No se compila a mano: lo hace "python construir.py", que le pasa estos valores:
;    /DVersionApp=3.7  /DCarpetaApp=...\dist\Lancelot  /DIcono=...\build\lancelot.ico
;    /DSalida=...\dist  /DMutexApp=LancelotEnEjecucion
;
;  Resultado: dist\Lancelot-setup-3.7.exe  (un solo archivo para instalar en cualquier PC)
;
;  Decisiones importantes:
;   - Se instala SOLO para tu usuario (%LOCALAPPDATA%\Programs\Lancelot): no pide permisos
;     de administrador, igual que VS Code o Spotify.
;   - Tus datos NO están aquí: viven en %LOCALAPPDATA%\Lancelot. Así, actualizar o reinstalar
;     nunca toca tus tareas. Al desinstalar, se te pregunta si también quieres borrarlos.
;   - AppId nunca debe cambiar: es como Windows sabe que la 3.8 es una actualización de la 3.7
;     y no un programa distinto.
; =============================================================================

#ifndef VersionApp
  #define VersionApp "0.0"
#endif
#ifndef CarpetaApp
  #define CarpetaApp "..\dist\Lancelot"
#endif
#ifndef Icono
  #define Icono "..\build\lancelot.ico"
#endif
#ifndef Salida
  #define Salida "..\dist"
#endif
#ifndef MutexApp
  #define MutexApp "LancelotEnEjecucion"
#endif

#define NombreApp "Lancelot"
#define ExeApp "Lancelot.exe"

[Setup]
AppId={{A0C5479E-06AA-4712-B076-98802BC57863}
AppName={#NombreApp}
AppVersion={#VersionApp}
AppVerName={#NombreApp} {#VersionApp}
AppPublisher=Miguel
VersionInfoVersion={#VersionApp}
VersionInfoDescription=Instalador de {#NombreApp}

; Instalación por usuario, sin administrador
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#NombreApp}
DisableProgramGroupPage=yes
DisableDirPage=auto
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Si Lancelot está abierto, el instalador lo detecta y pide cerrarlo
AppMutex={#MutexApp}
CloseApplications=yes

; Apariencia y salida
WizardStyle=modern
SetupIconFile={#Icono}
UninstallDisplayIcon={app}\{#ExeApp}
UninstallDisplayName={#NombreApp}
OutputDir={#Salida}
OutputBaseFilename={#NombreApp}-setup-{#VersionApp}

; Compresión fuerte: ~300 MB de programa quedan en un instalador mucho más chico
Compression=lzma2/max
SolidCompression=yes

[Languages]
; Spanish.isl viene con Inno Setup. Si no estuviera, el instalador sale en inglés.
#if FileExists(AddBackslash(CompilerPath) + "Languages\Spanish.isl")
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
#else
Name: "en"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "inicio"; Description: "Iniciar {#NombreApp} al encender la laptop"; GroupDescription: "Opciones:"
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Opciones:"; Flags: unchecked

[Files]
; Todo lo que creó PyInstaller. "ignoreversion": en una actualización se reemplaza siempre.
Source: "{#CarpetaApp}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Al actualizar, borra la carpeta interna vieja: así no quedan librerías de versiones anteriores
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#NombreApp}"; Filename: "{app}\{#ExeApp}"; Comment: "Tu asistente de tareas"
Name: "{autodesktop}\{#NombreApp}"; Filename: "{app}\{#ExeApp}"; Tasks: escritorio
Name: "{userstartup}\{#NombreApp}"; Filename: "{app}\{#ExeApp}"; Tasks: inicio

[Run]
Filename: "{app}\{#ExeApp}"; Description: "Abrir {#NombreApp} ahora"; Flags: nowait postinstall skipifsilent

[Code]
{ Al terminar de desinstalar: ¿borrar también los datos? Por defecto NO (botón "No" marcado).
  En una desinstalación silenciosa (sin ventanas) nunca se borran. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Datos: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Datos := ExpandConstant('{localappdata}\{#NombreApp}');
    if DirExists(Datos) and not UninstallSilent() then
      if MsgBox('¿Borrar también tus tareas, apodos, respaldos y voces?' + #13#10#13#10 + Datos + #13#10#13#10 +
                'Si vas a reinstalar Lancelot, elige "No" y los encontrará como los dejaste.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Datos, True, True, True);
  end;
end;
