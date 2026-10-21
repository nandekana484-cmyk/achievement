#Requires -RunAsAdministrator
# 【管理者権限が必要】PowerShell を「管理者として実行」してから動かす(タスクスケジューラから外すため)。
#
# install-autostart.ps1 で登録した自動起動を解除する。動いていれば止める。
#   .\uninstall-autostart.ps1
param([string]$TaskName = "GenbaApp")

$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "タスク「$TaskName」は登録されていません"
    return
}
Stop-ScheduledTask -TaskName $TaskName
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "解除しました: タスク「$TaskName」"
