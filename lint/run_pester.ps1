# Runs the Pester tests in tests/powershell and exits 1 if any fails.
# Usage: pwsh -NoProfile -File lint/run_pester.ps1
# The pinned Pester is imported by its exact path (see import_pinned_module.ps1). A
# configuration object is used instead of -CI so no testResults.xml is written.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'import_pinned_module.ps1')
Import-PinnedModule -Name 'Pester'
$configuration = New-PesterConfiguration
$configuration.Run.Path = Join-Path (Split-Path -Parent $PSScriptRoot) 'tests/powershell'
$configuration.Run.PassThru = $true
$configuration.Output.Verbosity = 'Detailed'
$result = Invoke-Pester -Configuration $configuration
# A test may have imported another copy of Pester; the run does not count if it did.
Assert-PinnedModule -Name 'Pester'
if ($result.Result -ne 'Passed') { exit 1 }
