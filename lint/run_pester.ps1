# Runs the Pester tests in tests/powershell and exits 1 if any fails.
# Usage: pwsh -NoProfile -File lint/run_pester.ps1
# The pinned Pester is imported by its exact path (see import_pinned_module.ps1). A
# configuration object is used instead of -CI so no testResults.xml is written.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'import_pinned_module.ps1')
Import-PinnedModule -Name 'Pester'
$configuration = New-PesterConfiguration
$configuration.Run.Path = Join-Path (Split-Path -Parent $PSScriptRoot) 'tests/powershell'
$configuration.Run.Exit = $true
$configuration.Output.Verbosity = 'Detailed'
Invoke-Pester -Configuration $configuration
