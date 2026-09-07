param(
    [string]$Python = "$PSScriptRoot\.venv\Scripts\python.exe",
    [string]$DistPath = 'dist'
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath $Python)) { throw 'Create .venv and install requirements-dev.txt first.' }
    & $Python -m PyInstaller --noconfirm --onedir --windowed --name FacebookGroupMonitor --collect-all customtkinter --collect-all playwright --distpath $DistPath --workpath build main.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    $taskOutput = Join-Path $DistPath 'FacebookGroupMonitor'
    Copy-Item -LiteralPath README.md -Destination (Join-Path $taskOutput 'README.md')
    Write-Host "Built: $taskOutput\FacebookGroupMonitor.exe"
    Write-Host 'Distribute the entire FacebookGroupMonitor folder, including _internal.'
} finally {
    Pop-Location
}
