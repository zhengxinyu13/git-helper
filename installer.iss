; Git 提交助手 —— Inno Setup 安装包脚本
; 编译方式（ISCC 路径按本机实际安装位置调整）：
;   ISCC.exe installer.iss
; 产物：installer\Git提交助手-Setup-<版本>.exe
;
; 说明：本助手本质是 git 的图形外壳，目标机器上必须装有 Git for Windows，
;       脚本会在安装完成后检测，没装就弹提示（不阻断安装）。

#define MyAppName "Git 提交助手"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "Grayson Zheng"
#define MyAppExeName "Git提交助手.exe"
#define MyCliExeName "GitHelper-CLI.exe"
; AppId 必须永远不变：升级时靠它认出旧版本，改了就会装成第二份
#define MyAppId "{967E7D85-8020-42D6-8F0B-866FA354AB62}"

; Git for Windows 安装包（本机没装 Git 时，安装助手可顺便联网下载安装）。
; 版本号 / 下载地址由 build_exe.py 在打包时自动刷新为最新稳定版；
; 这里留一个真实可用的默认值，手工 ISCC 也能编译。
#define GIT_VERSION "2.56.0.windows.4"
#define GIT_SETUP_URL "https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.4/Git-2.56.0.4-64-bit.exe"

[Setup]
AppId={{#MyAppId}
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
; 桌面快捷方式默认勾上：全新安装会创建；升级时由下面 [Icons] 的 Check 决定
; （已存在就不重写，从而保住图标位置）。
Name: "desktopicon"; Description: "在桌面创建快捷方式"; GroupDescription: "附加任务:"
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
; 关键：桌面图标已存在时绝不重写。资源管理器按「项目」记图标位置，
; .lnk 一被覆盖写就当成新项目，位置记忆失效，图标会掉到左上角第一个空位。
; 所以这里用 Check 兜住——存在就跳过，位置原样保留。
; 代价：这一条不会被写进卸载记录，卸载后可能残留一个失效的桌面图标。
Name: "{autodesktop}\Git 提交助手"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"; \
    Tasks: desktopicon; Check: not DesktopIconExists

[Registry]
; 命令行版加入 PATH：追加到用户级 PATH，不改动系统 PATH
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
    ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}'); Tasks: addtopath

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "安装完成后立即启动 Git 提交助手"; \
    Flags: nowait postinstall skipifsilent unchecked
; 本机没装 Git 且用户在「Git 安装」页勾选了 → 静默安装 Git for Windows。
; 文件由 NextButtonClick 阶段联网下载到 {tmp}，这里只负责跑它。
; 参数：/VERYSILENT 不弹 UI，/NORESTART 不重启，/NOCANCEL 不让用户中途取消。
Filename: "{tmp}\GitSetup.exe"; Parameters: "/VERYSILENT /NORESTART /NOCANCEL"; \
    Description: "正在安装 Git for Windows…"; \
    StatusMsg: "正在安装 Git for Windows，请稍候…"; \
    Flags: runhidden; Check: GitShouldInstall

[UninstallDelete]
; 只清理旧版本（<=1.0.3）遗留在程序目录里的运行时文件。
; 1.0.4 起用户配置改存 %APPDATA%\Git 提交助手\，卸载不会带走。
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\error.log"

[Code]
var
  OldVersion: string;
  GitPage: TInputOptionWizardPage;

{ 前向声明：下面这些函数在 InitializeWizard / NextButtonClick 里被提前调用，
  但定义放在更后面，所以这里先声明 }
function GitInstalled(): Boolean; forward;
function DownloadGit(): Boolean; forward;

function InstalledVersion(): string;
begin
  Result := '';
  if not RegQueryStringValue(HKEY_CURRENT_USER,
       'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1',
       'DisplayVersion', Result) then
    Result := '';
end;

{ 桌面快捷方式是否已经存在。存在就不重写，保住图标位置。 }
function DesktopIconExists(): Boolean;
begin
  Result := FileExists(ExpandConstant('{autodesktop}\{#MyAppName}.lnk'));
end;

procedure InitializeWizard();
var
  i: Integer;
begin
  OldVersion := InstalledVersion();
  if OldVersion = '' then
    exit;                       // 全新安装，文案用默认

  { 就地升级：只替换程序文件，不卸载、不动快捷方式、不动用户配置 }
  WizardForm.Caption := '升级 - {#MyAppName}';
  WizardForm.WelcomeLabel1.Caption := '欢迎使用 {#MyAppName} 升级向导';
  WizardForm.WelcomeLabel2.Caption :=
    '这台电脑上已经装有 {#MyAppName} ' + OldVersion + '，即将升级到 {#MyAppVersion}。' + #13#10 + #13#10 +
    '升级只替换程序文件：你的最近仓库记录、自动提交设置、玻璃浓度都会保留，' + #13#10 +
    '桌面图标的位置、开始菜单的快捷方式都不会被删除或移动。';
  WizardForm.FinishedHeadingLabel.Caption := '{#MyAppName} 升级完成';
  WizardForm.FinishedLabel.Caption :=
    '已升级到 {#MyAppVersion}。你的个人设置和快捷方式都原样保留。';

  { 桌面快捷方式已经存在 → 取消勾选，本升级不会去碰它，图标位置原地不动。
    不存在才勾上，让 [Icons] 建一个新的。 }
  for i := 0 to WizardForm.TasksList.Items.Count - 1 do
  begin
    if Pos('桌面', WizardForm.TasksList.ItemCaption[i]) > 0 then
      WizardForm.TasksList.Checked[i] := not DesktopIconExists();
  end;

  { 本机没装 Git：在「选择附加任务」页之后插一页，让用户决定是否顺便安装。
    默认勾选；用户取消也可以，软件打开后会用常驻横幅提示先装 Git。 }
  if not GitInstalled() then
  begin
    GitPage := CreateInputOptionPage(wpSelectTasks,
      'Git for Windows 未安装',
      'Git 提交助手依赖 Git 命令',
      'Git 提交助手是 git 的图形外壳，必须先装 Git 才能用。' + #13#10 +
      '建议勾选下面一项，安装时会联网下载并静默安装 Git for Windows（约 60MB）。' + #13#10 +
      '取消勾选也可以，之后你随时能自己装，软件打开后会提示你。',
      True, False);
    GitPage.Add('为这台电脑安装 Git for Windows（软件运行所必需）');
    GitPage.Values[0] := True;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  { 离开 Git 安装页、且用户勾选了 → 联网下载安装程序到临时目录（只下这一次） }
  if (GitPage <> nil) and (CurPageID = GitPage.ID) and GitPage.Values[0] then
  begin
    if not FileExists(ExpandConstant('{tmp}\GitSetup.exe')) then
    begin
      if not DownloadGit() then
      begin
        if MsgBox('下载 Git 安装程序失败，可能是网络问题。' + #13#10 +
                  '你可以稍后手动安装 Git for Windows：' + #13#10 +
                  '    https://git-scm.com/download/win' + #13#10 + #13#10 +
                  '仍要继续安装 Git 提交助手吗？（之后软件会提示你先装 Git）',
                  mbConfirmation, MB_YESNO) = IDNO then
          Result := False;
      end;
    end;
  end;
end;

function DownloadGit(): Boolean;
var
  URL, Dest, Params: string;
  ErrCode: Integer;
  ProgressPage: TOutputProgressWizardPage;
begin
  Result := False;
  URL := '{#GIT_SETUP_URL}';
  Dest := ExpandConstant('{tmp}\GitSetup.exe');
  ProgressPage := CreateOutputProgressPage('正在下载 Git for Windows',
    '请稍候，正在下载约 60MB 的安装程序（只需这一次）…');
  ProgressPage.SetProgress(0, 100);
  ProgressPage.Show();
  try
    Params := '-NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri ' +
              '''' + URL + '''' + ' -OutFile ' + '''' + Dest + '''' +
              ' -UseBasicParsing"';
    if Exec('powershell.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, ErrCode) then
      Result := (ErrCode = 0) and FileExists(Dest);
  finally
    ProgressPage.Hide();
    ProgressPage.Free();
  end;
end;

function GitShouldInstall(): Boolean;
begin
  Result := (GitPage <> nil) and GitPage.Values[0] and
            FileExists(ExpandConstant('{tmp}\GitSetup.exe'));
end;

procedure RegisterGitPath();
var
  GitCmd, PathVar: string;
begin
  { 把 Git 的 cmd 目录追加进用户级 PATH，这样命令行版和终端也能直接敲 git。
    Git 静默安装不一定会写 PATH（尤其 per-user 安装），这里补齐。 }
  GitCmd := '';
  if FileExists(ExpandConstant('{localappdata}\Programs\Git\cmd\git.exe')) then
    GitCmd := ExpandConstant('{localappdata}\Programs\Git\cmd')
  else if FileExists(ExpandConstant('{pf}\Git\cmd\git.exe')) then
    GitCmd := ExpandConstant('{pf}\Git\cmd')
  else if FileExists(ExpandConstant('{pf32}\Git\cmd\git.exe')) then
    GitCmd := ExpandConstant('{pf32}\Git\cmd');
  if GitCmd = '' then
    exit;
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', PathVar) then
    PathVar := '';
  if Pos(';' + Uppercase(GitCmd) + ';', ';' + Uppercase(PathVar) + ';') > 0 then
    exit;
  if PathVar = '' then
    PathVar := GitCmd
  else
    PathVar := PathVar + ';' + GitCmd;
  RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', PathVar);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpReady) and (OldVersion <> '') then
    WizardForm.NextButton.Caption := '升级(&U)';
end;

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
  if CurStep = ssPostInstall then
  begin
    { 用户勾选了顺带装 Git → 把 Git 的 cmd 目录补进用户 PATH }
    if GitShouldInstall() then
      RegisterGitPath();

    { 只有当用户没选装、且仍检测不到 Git 时，才弹提示（选了但下载/安装失败的情况，
      软件打开后会有常驻横幅兜底，这里不再重复打扰） }
    if (not GitInstalled()) and ((GitPage = nil) or (not GitPage.Values[0])) then
      MsgBox('没有在这台电脑上检测到 Git。' + #13#10 + #13#10 +
             'Git 提交助手是 git 的图形外壳，所有功能都依赖 git 命令。' + #13#10 +
             '请先安装 Git for Windows（一路下一步即可）：' + #13#10 +
             '    https://git-scm.com/download/win' + #13#10 + #13#10 +
             '装完 Git 后再打开本助手就能正常工作。',
             mbInformation, MB_OK);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  NewPath, AppPath: string;
  PosApp: Integer;
begin
  if CurUninstallStep <> usPostUninstall then
    exit;

  { 把安装时追加进 PATH 的那一段摘掉 }
  if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', NewPath) then
  begin
    AppPath := ExpandConstant('{app}');
    PosApp := Pos(';' + Uppercase(AppPath), Uppercase(NewPath));
    if PosApp > 0 then
    begin
      Delete(NewPath, PosApp, Length(AppPath) + 1);
      RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', NewPath);
    end;
  end;

  { 卸载删的是程序，不是个人数据 —— 明确告诉用户设置还在哪 }
  if not UninstallSilent then
    MsgBox('{#MyAppName} 已卸载。' + #13#10 + #13#10 +
           '你的个人设置（最近仓库、自动提交、玻璃浓度）保存在：' + #13#10 +
           '    ' + ExpandConstant('{userappdata}') + '\{#MyAppName}\config.json' + #13#10 + #13#10 +
           '以后再装回来会自动沿用，不用重新配置。',
           mbInformation, MB_OK);
end;
