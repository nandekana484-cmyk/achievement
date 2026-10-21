#Requires -RunAsAdministrator
# 【管理者権限が必要】PowerShell を「管理者として実行」してから動かす(ファイアウォールの設定を変えるため)。
#
# firewall-allow.ps1 で足した受信の許可を消す。
#   .\firewall-remove.ps1
param([string]$RuleName = "GenbaApp")

$ErrorActionPreference = "Stop"
$rules = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($null -eq $rules) {
    Write-Host "規則「$RuleName」はありません"
    return
}
$rules | Remove-NetFirewallRule
Write-Host "消しました: 規則「$RuleName」"
