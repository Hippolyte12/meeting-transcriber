; Meeting Transcriber — Script Inno Setup (avec Python embarqué)
; Compile ce fichier avec Inno Setup pour générer l'installeur

[Setup]
AppName=Meeting Transcriber
AppVersion=1.0.2
AppPublisher=Meeting Transcriber
DefaultDirName={localappdata}\MeetingTranscriber
DefaultGroupName=Meeting Transcriber
OutputDir=installer_output
OutputBaseFilename=MeetingTranscriber_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; Python embarqué
Source: "python_embed\*"; DestDir: "{app}\python_embed"; Flags: ignoreversion recursesubdirs

; Fichiers de l'application
Source: "app.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "setup_first_run.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "updater.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "version.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "MeetingTranscriber.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
; Pipeline
Source: "pipeline\*"; DestDir: "{app}\pipeline"; Flags: ignoreversion recursesubdirs

[Dirs]
Name: "{app}\models"
Name: "{app}\output"

[Icons]
; Raccourci bureau
Name: "{commondesktop}\Meeting Transcriber"; Filename: "{app}\MeetingTranscriber.bat"; WorkingDir: "{app}"; Comment: "Lancer Meeting Transcriber"
; Raccourci menu démarrer
Name: "{group}\Meeting Transcriber"; Filename: "{app}\MeetingTranscriber.bat"; WorkingDir: "{app}"
Name: "{group}\Désinstaller Meeting Transcriber"; Filename: "{uninstallexe}"

[Run]
; Proposer de lancer l'app après l'installation
Filename: "{app}\MeetingTranscriber.bat"; Description: "Lancer Meeting Transcriber"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Nettoyer les fichiers générés à la désinstallation
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\output"
Type: files; Name: "{app}\.installed"
