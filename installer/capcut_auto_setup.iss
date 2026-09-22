#define MyAppName "CapCut 자동 컷편집"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "capcut-auto"
#define MyAppExeName "run.bat"

[Setup]
AppId={{6F2C7B0E-6B0A-4E7B-9B34-1B8C6D6C2C11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\CapCutAuto
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=CapCutAuto_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\capcut_auto\*"; DestDir: "{app}\capcut_auto"; Excludes: "__pycache__,*.pyc"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "run.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "setup_env.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 아이콘:"; Flags: unchecked

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\setup_env.ps1"""; WorkingDir: "{app}"; StatusMsg: "필요한 프로그램(Python/ffmpeg)과 패키지를 설치하는 중입니다. 인터넷 상황에 따라 몇 분 걸릴 수 있습니다..."; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "지금 CapCut 자동 컷편집 실행하기"; WorkingDir: "{app}"; Flags: postinstall skipifsilent nowait shellexec

[UninstallDelete]
Type: filesandordirs; Name: "{app}\venv"
