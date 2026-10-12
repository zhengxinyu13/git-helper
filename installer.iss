; Git 提交助手 —— Inno Setup 安装包脚本
; 编译方式（ISCC 路径按本机实际安装位置调整）：
;   ISCC.exe installer.iss
; 产物：installer\Git提交助手-Setup-<版本>.exe
;
; 说明：本助手本质是 git 的图形外壳，目标机器上必须装有 Git for Windows，
;       脚本会在安装完成后检测，没装就弹提示（不阻断安装）。

#define MyAppName "Git 提交助手"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Grayson Zheng"
#define MyAppExeName "Git提交助手.exe"
#define MyCliExeName "GitHelper-CLI.exe"

[Setup]
AppId={{967E7D85-8020-42D6-8F0B-866FA354AB62}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\Git 提交助手
DefaultGroupName={#MyAppName}
DisableDirPage=auto
DisableProgramGroupPage=auto
; 装到当前用户可写的位置（默认 {localappdata}\Programs），
; 因为 config.json 要写在程序目录，放 Program Files 会因为权限写不进去。
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=Git提交助手-Setup-{#MyAppVersion}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 勾了「加入 PATH」后，装/卸都要广播 WM_SETTINGCHANGE，否则资源管理器
; 不会立刻感知 PATH 变化。这是 Inno 官方做法，比手写 SendMessageTimeout 稳。
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no

[Languages]
; Inno Setup 官方不带简体中文语言文件，且离线环境下下不到，
; 这里用英文语言 + 下面的 [Messages] 段把向导文案逐条改成中文。
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
SetupWindowTitle=安装 - %1
SetupAppTitle=安装
UninstallAppFullTitle=%1 卸载
UninstallAppTitle=卸载
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonFinish=完成(&F)
ButtonCancel=取消
ButtonYes=是(&Y)
ButtonNo=否(&N)
ButtonOK=确定
ButtonBrowse=浏览(&R)...
WelcomeLabel1=欢迎使用 [name] 安装向导
WelcomeLabel2=本向导将把 [name]（版本 [ver]）安装到你的电脑。%n%n建议在安装前关闭其它正在运行的应用程序。
WizardSelectDir=选择安装位置
SelectDirLabel3=安装程序将把 [name] 安装到下面的文件夹。
SelectDirBrowseLabel=点击「下一步」继续。如果想换一个文件夹，点击「浏览」。
WizardSelectTasks=选择附加任务
SelectTasksLabel2=需要执行哪些附加任务？
SelectTasksDesc=选择安装过程中要执行的附加任务，然后点击「下一步」。
WizardReady=准备安装
ReadyLabel1=安装程序已准备好，即将把 [name] 安装到你的电脑。
ReadyLabel2a=点击「安装」开始安装；如果要检查或修改设置，点击「上一步」。
WizardPreparing=正在准备安装
PreparingDesc=安装程序正在为安装 [name] 做准备。
WizardInstalling=正在安装
InstallingLabel=正在安装 [name]，请稍候...
FinishedHeadingLabel=[name] 安装完成
FinishedLabelNoIcons=安装程序已在你的电脑上完成 [name] 的安装。
FinishedLabel=安装程序已在你的电脑上完成 [name] 的安装。可以通过已创建的快捷方式启动它。
ClickFinish=点击「完成」退出安装向导。
FinishedRestartLabel=...
FinishedRestartMessage=...
WizardSelectProgramGroup=选择开始菜单文件夹
SelectStartMenuFolderLabel3=安装程序应在哪个开始菜单文件夹中创建快捷方式？
ExitSetupTitle=退出安装
ExitSetupMessage=安装尚未完成。如果现在退出，[name] 将不会被安装。%n%n你可以稍后再次运行安装程序来完成安装。

[Tasks]
Name: "desktopicon"; Description: "在桌面创建快捷方式"; GroupDescription: "附加任务:"; Flags: unchecked
Name: "addtopath"; Description: "把命令行版加入 PATH（供脚本 / AI 调用）"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#MyCliExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "app.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "git_helper.py"; DestDir: "{app}\source"; Flags: ignoreversion
Source: "gitcore.py"; DestDir: "{app}\source"; Flags: ignoreversion
Source: "gui_qt.py"; DestDir: "{app}\source"; Flags: ignoreversion
Source: "gui_main.py"; DestDir: "{app}\source"; Flags: ignoreversion

[Icons]
Name: "{group}\Git 提交助手"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"
Name: "{group}\命令行版（CLI）使用说明"; Filename: "{app}\{#MyCliExeName}"; Parameters: "help"; IconFilename: "{app}\app.ico"
Name: "{group}\卸载 Git 提交助手"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Git 提交助手"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Registry]
; 命令行版加入 PATH：追加到用户级 PATH，不改动系统 PATH
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
    ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}'); Tasks: addtopath

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "安装完成后立即启动 Git 提交助手"; \
    Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\error.log"

[Code]
function GitInstalled(): Boolean;
var
  s: string;
begin
  Result := False;
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\GitForWindows', 'InstallPath', s) then
  begin
    if (s <> '') and (FileExists(s + '\cmd\git.exe') or FileExists(s + '\bin\git.exe')) then
    begin
      Result := True;
      exit;
    end;
  end;
  if FileExists(ExpandConstant('{pf}\Git\cmd\git.exe')) or
     FileExists(ExpandConstant('{pf32}\Git\cmd\git.exe')) or
     FileExists(ExpandConstant('{cmd}\git.exe')) then
    Result := True;
end;

function NeedsAddPath(Param: string): Boolean;
var
  OldPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OldPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Param) + ';', ';' + Uppercase(OldPath) + ';') = 0;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not GitInstalled()) then
    MsgBox('没有在这台电脑上检测到 Git。' + #13#10 + #13#10 +
           'Git 提交助手是 git 的图形外壳，所有功能都依赖 git 命令。' + #13#10 +
           '请先安装 Git for Windows（一路下一步即可）：' + #13#10 +
           '    https://git-scm.com/download/win' + #13#10 + #13#10 +
           '装完 Git 后再打开本助手就能正常工作。',
           mbInformation, MB_OK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  NewPath, AppPath: string;
  PosApp: Integer;
begin
  if CurUninstallStep <> usPostUninstall then
    exit;
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', NewPath) then
    exit;
  AppPath := ExpandConstant('{app}');
  PosApp := Pos(';' + Uppercase(AppPath), Uppercase(NewPath));
  if PosApp > 0 then
  begin
    Delete(NewPath, PosApp, Length(AppPath) + 1);
    RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', NewPath);
  end;
end;
