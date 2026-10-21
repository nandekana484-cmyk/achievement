#Requires -RunAsAdministrator
# 【管理者権限が必要】PowerShell を「管理者として実行」してから動かす(タスクスケジューラに登録するため)。
#
# 本アプリ(exe)を、PCの起動時に自動で起動するよう、タスクスケジューラに登録する(担当者PCで使う)。
#   .\install-autostart.ps1 -Version v1.0.0                      # SYSTEM で動かす(ログオンしていなくても動く)
#   .\install-autostart.ps1 -Version v1.0.0 -User "DOMAIN\genba"  # 指定した利用者で動かす(パスワードを聞く)
# 版を更新したら、新しい版で登録し直す(同じ名前のタスクは置き換わる)。
# backup_dir が共有フォルダのとき、SYSTEM はこのPCのコンピューターアカウントで接続する。
# 共有フォルダにそのアカウントの書き込み権限が無ければ -User で動かす。詳細: docs/design/packaging.md
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$GenbaHome = "C:\GenbaApp",
    [string]$TaskName = "GenbaApp",
    [string]$User
)

$ErrorActionPreference = "Stop"
$Exe = Join-Path $GenbaHome "app\$Version\GenbaApp.exe"
if (-not (Test-Path $Exe)) { throw "exe が見つかりません: $Exe" }

$action = New-ScheduledTaskAction -Execute $Exe -WorkingDirectory (Split-Path $Exe)
$trigger = New-ScheduledTaskTrigger -AtStartup
# 止まったら1分後に起動し直す。動き続けるので、実行時間の上限は無くす
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

if ($User) {
    $cred = Get-Credential -UserName $User -Message "タスクを動かす利用者のパスワード"
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest `
        -User $cred.UserName -Password $cred.GetNetworkCredential().Password -Force | Out-Null
} else {
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
}
Write-Host "登録しました: タスク「$TaskName」→ $Exe(PCの起動時に起動)"
Write-Host "今すぐ起動するには: Start-ScheduledTask -TaskName $TaskName"
