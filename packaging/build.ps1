# 本番に置く版(exe のフォルダと zip)を作る。開発者PCで、リポジトリ直下から実行する:
#   powershell -ExecutionPolicy Bypass -File .\packaging\build.ps1 [-SkipTests] [-Console]
# 手順: 画面のビルド → テスト → PyInstaller → packaging\dist\v<版>\ と packaging\dist\GenbaApp-v<版>.zip
# 標準はウィンドウを出さない形。-Console を付けると、コンソールを出す形を v<版>-console に作る(困ったときの確認用)。
# 版は backend\app\__init__.py の __version__。詳細: docs/design/packaging.md
param([switch]$SkipTests, [switch]$Console)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
$Dist = Join-Path $PSScriptRoot "dist"

# 外部のコマンドを動かし、失敗したら止める(PowerShell 5.1 は外部のコマンドの失敗で止まらないため)
function Invoke-Native([string]$Name, [string]$Dir, [scriptblock]$Command) {
    Write-Host "== $Name" -ForegroundColor Cyan
    Push-Location $Dir
    try {
        $global:LASTEXITCODE = 0
        & $Command
        if ($LASTEXITCODE -ne 0) { throw "$Name に失敗しました(終了コード $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
}

if (-not (Test-Path $Python)) { throw "backend\.venv が見つかりません(README の「開発環境の準備」)" }
$Version = (& $Python -c "import sys; sys.path.insert(0, r'$Root\backend'); from app import __version__; print(__version__)").Trim()
$Name = if ($Console) { "v$Version-console" } else { "v$Version" }
Write-Host "版: $Name"

Invoke-Native "画面のビルド" (Join-Path $Root "frontend") { npm run build }
if (-not $SkipTests) {
    Invoke-Native "バックエンドのテスト" (Join-Path $Root "backend") { & $Python -m pytest -q }
    Invoke-Native "画面のテスト(vitest)" (Join-Path $Root "frontend") { npm test }
}
$env:GENBA_CONSOLE = if ($Console) { "1" } else { "0" }  # packaging\genba.spec が読む
try {
    Invoke-Native "PyInstaller" $Root {
        & $Python -m PyInstaller --noconfirm --clean --log-level WARN `
            --distpath $Dist --workpath (Join-Path $PSScriptRoot "build") (Join-Path $PSScriptRoot "genba.spec")
    }
} finally {
    Remove-Item Env:GENBA_CONSOLE -ErrorAction SilentlyContinue
}

$Folder = Join-Path $Dist $Name
$Zip = Join-Path $Dist "GenbaApp-$Name.zip"
Write-Host "== zip" -ForegroundColor Cyan
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path $Folder -DestinationPath $Zip  # 中は v<版>\ のフォルダ。C:\GenbaApp\app\ に展開する

$FolderMB = [math]::Round(((Get-ChildItem $Folder -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
$ZipMB = [math]::Round((Get-Item $Zip).Length / 1MB, 1)
Write-Host "できました: $Folder($FolderMB MB)、$Zip($ZipMB MB)" -ForegroundColor Green
