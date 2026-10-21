#Requires -RunAsAdministrator
# 【管理者権限が必要】PowerShell を「管理者として実行」してから動かす(タスクスケジューラに登録するため)。
#
# 本アプリ(exe)を、PCの起動時に自動で起動するよう、タスクスケジューラに登録する(担当者PCで使う)。
# 標準: 担当者のアカウントで「ユーザーがログオンしているかどうかにかかわらず実行する」タスクにする。
#   - ウィンドウは出ない。担当者の権限で動くので、担当者が書ける共有フォルダにバックアップを書ける
#   - パスワードはスクリプトに書かない。実行したときに入力する(タスクスケジューラが保存する)
#   - 担当者のパスワードを変えたら、登録し直す(古いパスワードのままだと起動しない)
#
#   .\install-autostart.ps1 -Version v1.0.0                        # 今の利用者のアカウントで動かす
#   .\install-autostart.ps1 -Version v1.0.0 -User "DOMAIN\tantou"  # 担当者のアカウントを指定する
#   .\install-autostart.ps1 -Version v1.0.0 -RunAsSystem           # SYSTEM で動かす(パスワードは要らない)
#
# 【SYSTEM で動かすときの注意】共有フォルダには、このPCのコンピューターアカウント(DOMAIN\<PC名>$)で接続する。
# 共有フォルダにそのアカウントの書き込み権限が無いと、バックアップは取れない(アプリは止まらず、ログに警告が出る)。
# 版を更新したら、新しい版で登録し直す(同じ名前のタスクは置き換わる)。詳細: docs/design/packaging.md
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$GenbaHome = "C:\GenbaApp",
    [string]$TaskName = "GenbaApp",
    [string]$User = "$env:USERDOMAIN\$env:USERNAME",
    [switch]$RunAsSystem
)

$ErrorActionPreference = "Stop"
$Exe = Join-Path $GenbaHome "app\$Version\GenbaApp.exe"
if (-not (Test-Path $Exe)) { throw "exe が見つかりません: $Exe" }

$action = New-ScheduledTaskAction -Execute $Exe -WorkingDirectory (Split-Path $Exe)
$trigger = New-ScheduledTaskTrigger -AtStartup
# 止まったら1分後に起動し直す。動き続けるので、実行時間の上限は無くす
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

if ($RunAsSystem) {
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    $runAs = "SYSTEM"
} else {
    $cred = Get-Credential -UserName $User -Message "タスクを動かす担当者のアカウントのパスワードを入れてください"
    if ($null -eq $cred) { throw "パスワードが入力されなかったため、登録しませんでした" }
    # -User と -Password を渡すと「ユーザーがログオンしているかどうかにかかわらず実行する」になる(ウィンドウは出ない)
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited `
        -User $cred.UserName -Password $cred.GetNetworkCredential().Password -Force | Out-Null
    $runAs = $cred.UserName
}
Write-Host "登録しました: タスク「$TaskName」→ $Exe(PCの起動時に、$runAs で起動)"
Write-Host "今すぐ起動するには: Start-ScheduledTask -TaskName $TaskName"
