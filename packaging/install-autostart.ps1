#Requires -RunAsAdministrator
# 【管理者権限が必要】PowerShell を「管理者として実行」してから動かす(タスクスケジューラに登録するため)。
#
# 本アプリ(exe)を、PCの起動時に自動で起動するよう、タスクスケジューラに登録する(担当者PCで使う)。
# 「ユーザーがログオンしているかどうかにかかわらず実行する」タスクにする。実行するアカウント(-User)は必ず指定する。
#   - 管理者権限を持たない、このアプリ専用のアカウントを使う。SYSTEM や Administrator では動かさない(詳細: docs/design/security.md S-05)
#   - ウィンドウは出ない。そのアカウントの権限で動くので、そのアカウントが書ける共有フォルダにバックアップを書ける
#   - パスワードはスクリプトに書かない。実行したときに入力する(タスクスケジューラが保存する)
#   - そのアカウントのパスワードを変えたら、登録し直す(古いパスワードのままだと起動しない)
#
#   .\install-autostart.ps1 -Version v1.0.0 -User "DOMAIN\genba-app"
#
# アカウントの権限(C:\GenbaApp のフォルダ、バックアップ先の共有フォルダ)の決め方は docs/design/packaging.md。
# 版を更新したら、新しい版で登録し直す(同じ名前のタスクは置き換わる)。
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$User,
    [string]$GenbaHome = "C:\GenbaApp",
    [string]$TaskName = "GenbaApp"
)

$ErrorActionPreference = "Stop"
if ($User -match '^(NT AUTHORITY\\)?(SYSTEM|LOCAL SERVICE|NETWORK SERVICE)$' -or $User -match '(^|\\)Administrator$') {
    throw "SYSTEM や Administrator では動かしません。管理者権限を持たない専用のアカウントを -User に指定してください(docs/design/security.md S-05)"
}
$Exe = Join-Path $GenbaHome "app\$Version\GenbaApp.exe"
if (-not (Test-Path $Exe)) { throw "exe が見つかりません: $Exe" }

$action = New-ScheduledTaskAction -Execute $Exe -WorkingDirectory (Split-Path $Exe)
$trigger = New-ScheduledTaskTrigger -AtStartup
# 止まったら1分後に起動し直す。動き続けるので、実行時間の上限は無くす
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

$cred = Get-Credential -UserName $User -Message "タスクを動かすアカウントのパスワードを入れてください"
if ($null -eq $cred) { throw "パスワードが入力されなかったため、登録しませんでした" }
try {
    $members = @(Get-LocalGroupMember -Group "Administrators" -ErrorAction Stop | Where-Object { $_.Name -ieq $cred.UserName })
    if ($members.Count -gt 0) { Write-Warning "$($cred.UserName) は Administrators のメンバーです。権限を絞った専用のアカウントにしてください" }
} catch { }  # グループを調べられないとき(ドメインのアカウントなど)は、この確認を省く
# -User と -Password を渡すと「ユーザーがログオンしているかどうかにかかわらず実行する」になる(ウィンドウは出ない)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited `
    -User $cred.UserName -Password $cred.GetNetworkCredential().Password -Force | Out-Null
Write-Host "登録しました: タスク「$TaskName」→ $Exe(PCの起動時に、$($cred.UserName) で起動)"
Write-Host "今すぐ起動するには: Start-ScheduledTask -TaskName $TaskName"
