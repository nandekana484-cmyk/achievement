#Requires -RunAsAdministrator
# 【管理者権限が必要】PowerShell を「管理者として実行」してから動かす(ファイアウォールの設定を変えるため)。
#
# 本アプリのポートだけ、社内LANからの受信を許可する(担当者PCで使う)。ほかのポートは開けない。
#   .\firewall-allow.ps1 -Port 8000
# ポートは config.toml の server.port と合わせる。プロファイルはドメインとプライベートだけ(パブリックでは開けない)。
# 受信を許す相手は -RemoteAddress で絞る。既定は LocalSubnet(このPCと同じサブネット)。
#   .\firewall-allow.ps1 -Port 8000 -RemoteAddress 192.168.10.0/24
#   .\firewall-allow.ps1 -Port 8000 -RemoteAddress 192.168.10.21,192.168.10.22   # タブレットと管理用PCだけ
# 詳細: docs/design/security.md(S-04)
param(
    [int]$Port = 8000,
    [string[]]$RemoteAddress = @("LocalSubnet"),
    [string]$RuleName = "GenbaApp"
)

$ErrorActionPreference = "Stop"
Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule  # 入れ直すときのため
New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port `
    -RemoteAddress $RemoteAddress -Profile Domain, Private | Out-Null
Write-Host "許可しました: 受信 TCP $Port、相手 $($RemoteAddress -join ', ')(規則の名前「$RuleName」)"
