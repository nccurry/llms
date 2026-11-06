# Runs the Pester tests in tests/powershell and exits 1 if any fails.
# Usage: pwsh -NoProfile -File lint/run_pester.ps1
# PSModulePath must name the folder that holds the pinned Pester (the test:powershell task
# sets it). A configuration object is used instead of -CI so no testResults.xml is written.
$ErrorActionPreference = 'Stop'
Import-Module Pester
$configuration = New-PesterConfiguration
$configuration.Run.Path = Join-Path (Split-Path -Parent $PSScriptRoot) 'tests/powershell'
$configuration.Run.Exit = $true
$configuration.Output.Verbosity = 'Detailed'
Invoke-Pester -Configuration $configuration
