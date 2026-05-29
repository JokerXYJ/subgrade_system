; installer.iss
[Setup]
AppName=公路路基压实度实时监测与薄弱区识别系统
AppVersion=1.0.0
DefaultDirName={autopf}\SubgradeCompactionSystem
DefaultGroupName=公路路基压实度监测系统
OutputDir=.
OutputBaseFilename=SubgradeCompactionSystem_Setup
Compression=lzma
SolidCompression=yes
DisableProgramGroupPage=yes
AlwaysCreateUninstallIcon=yes

[Files]
Source: "dist\main\main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\公路路基压实度实时监测系统"; Filename: "{app}\main.exe"
Name: "{commondesktop}\公路路基压实度实时监测系统"; Filename: "{app}\main.exe"

[Run]
Filename: "{app}\main.exe"; Description: "运行 公路路基压实度实时监测系统"; Flags: postinstall nowait skipifsilent