param(
    [string]$ExePath = "$PSScriptRoot\dist\windows-startup\FacebookGroupMonitor\FacebookGroupMonitor.exe",
    [switch]$Disable
)
$ErrorActionPreference = 'Stop'
$registryPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$entryName = 'FacebookGroupMonitor'
if ($Disable) {
    Remove-ItemProperty -LiteralPath $registryPath -Name $entryName -ErrorAction SilentlyContinue
    Write-Host 'Windows startup disabled.'
    exit
}
$resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
if ([IO.Path]::GetExtension($resolvedExe) -ne '.exe' -or $resolvedExe.Contains('"')) {
    throw 'Expected an executable path.'
}
New-Item -Path $registryPath -Force | Out-Null
$startupCommand = '"' + $resolvedExe + '" --autostart'
New-ItemProperty -LiteralPath $registryPath -Name $entryName -Value $startupCommand -PropertyType String -Force | Out-Null
Write-Host "Windows startup enabled: $startupCommand"
