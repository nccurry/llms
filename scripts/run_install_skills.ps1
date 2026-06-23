$ErrorActionPreference = "Stop"

function Test-PythonCommand {
    param([string]$Command)

    try {
        & $Command --version *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

$python = $null

if ($env:PYTHON -and (Test-PythonCommand $env:PYTHON)) {
    $python = $env:PYTHON
}
elseif (Test-PythonCommand "python") {
    $python = "python"
}
elseif (Test-PythonCommand "python3") {
    $python = "python3"
}
else {
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $bundled) {
        $python = $bundled
    }
}

if (-not $python) {
    Write-Error "Python was not found. Set PYTHON to a Python executable, then retry."
    exit 127
}

$script = Join-Path $PSScriptRoot "install_skills.py"
& $python $script @args
exit $LASTEXITCODE
