#requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('Device', 'Check', 'Tests')]
    [string]$Mode = 'Device',
    [string]$SdkPath,
    [string]$DeveloperKey
)
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$ciqData = Join-Path $env:APPDATA 'Garmin\ConnectIQ'
$toolDir = Join-Path $env:LOCALAPPDATA 'Garmin\ThisIsFineToolchain'
$previousPath = $env:Path
Push-Location -LiteralPath $project
try {
    $candidates = @($SdkPath, $env:CIQ_HOME)
    $activeCfg = Join-Path $ciqData 'current-sdk.cfg'
    if (Test-Path -LiteralPath $activeCfg) { $candidates += (Get-Content -Raw -LiteralPath $activeCfg).Trim() }
    $candidates += Join-Path $toolDir 'sdk-9.3.0'
    $compiler = $null
    foreach ($candidate in $candidates) {
        if (!$candidate) { continue }
        $possible = Join-Path $candidate 'bin\monkeyc.bat'
        if (Test-Path -LiteralPath $possible) { $compiler = $possible; break }
    }
    if (!$compiler) { $compiler = (Get-Command monkeyc.bat -ErrorAction SilentlyContinue).Source }
    if (!$compiler) { throw 'Install the Garmin Connect IQ SDK or pass -SdkPath pointing to the SDK folder.' }

    if (!(Get-Command java.exe -ErrorAction SilentlyContinue)) {
        $jdks = @($env:JAVA_HOME)
        $userJdks = Join-Path $env:USERPROFILE '.jdks'
        if (Test-Path -LiteralPath $userJdks) {
            $jdks += (Get-ChildItem -Directory -LiteralPath $userJdks | Sort-Object LastWriteTime -Descending).FullName
        }
        foreach ($jdk in $jdks) {
            if ($jdk -and (Test-Path -LiteralPath (Join-Path $jdk 'bin\java.exe'))) {
                $env:Path = (Join-Path $jdk 'bin') + [IO.Path]::PathSeparator + $env:Path
                break
            }
        }
        if (!(Get-Command java.exe -ErrorAction SilentlyContinue)) { throw 'Put Java 11 or later on PATH, or set JAVA_HOME.' }
    }
    if ($Mode -ne 'Check' -and !(Test-Path -LiteralPath (Join-Path $ciqData 'Devices\fenix6pro\compiler.json'))) {
        throw 'Download the fenix 6 Pro / 6 Sapphire device in Garmin SDK Manager > Devices. For an offline compiler check, use -Mode Check.'
    }
    if (!$DeveloperKey) {
        $keyDir = Join-Path $env:LOCALAPPDATA 'Garmin\ThisIsFine'
        $DeveloperKey = Join-Path $keyDir 'developer_key.der'
        if (!(Test-Path -LiteralPath $DeveloperKey)) {
            [IO.Directory]::CreateDirectory($keyDir) | Out-Null
            $rsa = [Security.Cryptography.RSA]::Create(4096)
            try {
                $stream = [IO.File]::Open($DeveloperKey, [IO.FileMode]::CreateNew)
                try {
                    $bytes = $rsa.ExportPkcs8PrivateKey()
                    $stream.Write($bytes, 0, $bytes.Length)
                } finally { $stream.Dispose() }
            } finally { $rsa.Dispose() }
        }
    }
    if (!(Test-Path -LiteralPath $DeveloperKey -PathType Leaf)) { throw 'The signing key file could not be found.' }

    $dest = switch ($Mode) {
        'Device' { 'bin\ThisIsFine.prg' }
        'Tests'  { 'build\tests\ThisIsFine-tests.prg' }
        'Check'  { 'build\check\compiler-check.prg' }
    }
    [IO.Directory]::CreateDirectory((Join-Path $project (Split-Path $dest -Parent))) | Out-Null
    $flags = @('-f', 'monkey.jungle', '-y', $DeveloperKey, '-o', $dest, '-w', '-l', '3', '--build-stats', '0')
    if ($Mode -ne 'Check') { $flags += @('-d', 'fenix6pro') }
    if ($Mode -eq 'Device') { $flags += '-r' } else { $flags += '-t' }
    & $compiler @flags
    if ($LASTEXITCODE -ne 0) { throw "Garmin compiler failed with exit code $LASTEXITCODE." }
    if ($Mode -eq 'Check') { Write-Output 'Compiler check passed. Use Device mode for a file to install on the watch.' }
    else { Write-Output (Join-Path $project $dest) }
} finally {
    $env:Path = $previousPath
    Pop-Location
}
