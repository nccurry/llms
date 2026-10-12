$TaskArguments = @($args)

# Windows PowerShell 5.1 rewrites embedded quotes in native array arguments.
# Build a Windows command line explicitly and let the child inherit stdio.
function ConvertTo-WindowsArgument {
    param([AllowEmptyString()][string] $Argument)
    $escaped = [regex]::Replace($Argument, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function Invoke-Mise {
    param([string[]] $Arguments, [switch] $CaptureOutput)
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $misePath
    $startInfo.Arguments = ($Arguments | ForEach-Object { ConvertTo-WindowsArgument $_ }) -join ' '
    $startInfo.UseShellExecute = $false
    $startInfo.WorkingDirectory = $repoRoot
    $startInfo.RedirectStandardOutput = [bool] $CaptureOutput
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        [void] $process.Start()
        $output = if ($CaptureOutput) { $process.StandardOutput.ReadToEnd() } else { '' }
        $process.WaitForExit()
        return [pscustomobject] @{ ExitCode = $process.ExitCode; Output = $output }
    }
    finally {
        $process.Dispose()
    }
}

$environmentBefore = @{}
$environmentNames = @(
    'PATH', 'PSModulePath', 'LLMS_ORIGINAL_PATH', 'LLMS_CALLER_CWD',
    'MISE_DATA_DIR', 'MISE_CACHE_DIR', 'MISE_CONFIG_DIR', 'MISE_STATE_DIR',
    'MISE_SYSTEM_CONFIG_DIR', 'MISE_CEILING_PATHS', 'MISE_TMP_DIR',
    'UV_PYTHON_INSTALL_DIR', 'UV_CACHE_DIR'
)
foreach ($name in $environmentNames) {
    $environmentBefore[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    $env:PSModulePath = "$PSHOME/Modules;$env:PSModulePath"
    $repoRoot = $PSScriptRoot
    if (-not $env:LLMS_ORIGINAL_PATH) { $env:LLMS_ORIGINAL_PATH = $env:PATH }
    if (-not $env:LLMS_CALLER_CWD) { $env:LLMS_CALLER_CWD = (Get-Location).Path }
    if ($env:OS -ne 'Windows_NT') {
        throw 'Use bootstrap.sh on Linux/macOS or bootstrap.ps1 on Windows.'
    }

    $architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
    $platform = switch ($architecture) {
        'AMD64' { 'windows-x64' }
        'ARM64' { 'windows-arm64' }
        default { throw "Unsupported CPU: $architecture" }
    }

    $env:MISE_DATA_DIR = Join-Path $repoRoot '.tools/mise/data'
    $env:MISE_CACHE_DIR = Join-Path $repoRoot '.tools/mise/cache'
    $env:MISE_CONFIG_DIR = Join-Path $repoRoot '.tools/mise/config'
    $env:MISE_STATE_DIR = Join-Path $repoRoot '.tools/mise/state'
    $env:MISE_SYSTEM_CONFIG_DIR = Join-Path $repoRoot '.tools/mise/system'
    $env:MISE_CEILING_PATHS = Split-Path $repoRoot -Parent
    $env:MISE_TMP_DIR = Join-Path $repoRoot '.tools/tmp'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $repoRoot '.tools/python'
    $env:UV_CACHE_DIR = Join-Path $repoRoot '.tools/uv-cache'
    $binDirectory = Join-Path $repoRoot '.tools/bin'
    New-Item -ItemType Directory -Force $binDirectory, $env:MISE_TMP_DIR | Out-Null
    $windowsCommands = Join-Path $env:SystemRoot 'System32'
    $windowsPowerShell = Join-Path $windowsCommands 'WindowsPowerShell/v1.0'
    $env:PATH = "$binDirectory;$windowsCommands;$windowsPowerShell;$env:PATH"

    $configuration = [IO.File]::ReadAllText((Join-Path $repoRoot 'mise.toml'))
    $miseVersion = [regex]::Match($configuration, '(?m)^mise_version = "([0-9.]+)"\r?$').Groups[1].Value
    if (-not $miseVersion) { throw 'mise.toml must pin vars.mise_version to an exact release.' }
    $misePath = Join-Path $binDirectory 'mise.exe'
    $miseShimPath = Join-Path $binDirectory 'mise-shim.exe'
    $installedVersion = ''
    if (Test-Path -LiteralPath $misePath) {
        $versionResult = Invoke-Mise -Arguments @('--version') -CaptureOutput
        if ($versionResult.ExitCode -eq 0) { $installedVersion = $versionResult.Output.Trim().Split(' ')[0] }
    }

    if ($installedVersion -ne $miseVersion -or -not (Test-Path -LiteralPath $miseShimPath)) {
        $temporaryDirectory = Join-Path $env:MISE_TMP_DIR "mise-$([guid]::NewGuid().ToString('N'))"
        New-Item -ItemType Directory $temporaryDirectory | Out-Null
        try {
            $asset = "mise-v$miseVersion-$platform.zip"
            $release = "https://github.com/jdx/mise/releases/download/v$miseVersion"
            $archive = Join-Path $temporaryDirectory $asset
            $checksums = Join-Path $temporaryDirectory 'checksums'
            Write-Host "Installing project-local mise $miseVersion"
            Invoke-WebRequest -UseBasicParsing -Uri "$release/$asset" -OutFile $archive
            Invoke-WebRequest -UseBasicParsing -Uri "$release/SHASUMS256.txt" -OutFile $checksums
            $pattern = '(?m)^([0-9a-f]{64})\s+\./' + [regex]::Escape($asset) + '\r?$'
            $expectedHash = [regex]::Match([IO.File]::ReadAllText($checksums), $pattern).Groups[1].Value
            if (-not $expectedHash -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expectedHash) {
                throw "Release checksum verification failed for $asset."
            }
            Expand-Archive -LiteralPath $archive -DestinationPath $temporaryDirectory
            $executable = Get-ChildItem -LiteralPath $temporaryDirectory -Filter mise.exe -Recurse -File | Select-Object -First 1
            if ($null -eq $executable) { throw "mise.exe was not found in $asset." }
            $shim = Join-Path $executable.DirectoryName 'mise-shim.exe'
            if (-not (Test-Path -LiteralPath $shim)) { throw "mise-shim.exe was not found in $asset." }
            Copy-Item -LiteralPath $executable.FullName -Destination $misePath -Force
            Copy-Item -LiteralPath $shim -Destination $miseShimPath -Force
        }
        finally {
            Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
        }
    }

    Push-Location $repoRoot
    try {
        $trustResult = Invoke-Mise -Arguments @('trust', '--yes', '--quiet', 'mise.toml')
        if ($trustResult.ExitCode -ne 0) { exit $trustResult.ExitCode }
        $installResult = Invoke-Mise -Arguments @('install', 'task', '--locked', '--quiet')
        if ($installResult.ExitCode -ne 0) { exit $installResult.ExitCode }

        $taskCommand = Join-Path $binDirectory 'task.cmd'
        if (-not (Test-Path -LiteralPath $taskCommand)) {
            @'
@echo off
if "%~1"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\bootstrap.ps1" default
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\bootstrap.ps1" %*
)
'@ | Set-Content -LiteralPath $taskCommand -Encoding Ascii
        }

        if ($TaskArguments.Count -eq 0) { $TaskArguments = @('deps:install') }
        $taskResult = Invoke-Mise -Arguments (@('exec', '--', 'task') + $TaskArguments)
        exit $taskResult.ExitCode
    }
    finally {
        Pop-Location
    }
}
finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $environmentBefore[$name], 'Process')
    }
}
