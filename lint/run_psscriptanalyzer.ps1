# Runs PSScriptAnalyzer on every tracked .ps1 file and exits 1 on any finding.
# Usage: pwsh -NoProfile -File lint/run_psscriptanalyzer.ps1
# PSModulePath must name only the folder that holds the pinned PSScriptAnalyzer
# (the lint:powershell task sets it).
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$settings = Join-Path $PSScriptRoot 'PSScriptAnalyzerSettings.psd1'
Import-Module PSScriptAnalyzer
$files = @(git -C $repoRoot ls-files '*.ps1')
if ($LASTEXITCODE -ne 0 -or $files.Count -eq 0) { throw 'git ls-files found no .ps1 files.' }
Write-Output "PSScriptAnalyzer $((Get-Module PSScriptAnalyzer).Version) on $($files.Count) files"
$findings = @()
foreach ($file in $files) {
    $analyzerArguments = @{ Path = (Join-Path $repoRoot $file); Settings = $settings }
    # The Pester tests and the scripts in lint/ run under PowerShell 7 and call Pester and
    # PSScriptAnalyzer commands that no 5.1 profile lists, so the command-compatibility rule
    # applies to the other files, which run on Windows PowerShell 5.1.
    if ($file -like '*.Tests.ps1' -or $file -like 'lint/*') { $analyzerArguments.ExcludeRule = @('PSUseCompatibleCommands') }
    foreach ($finding in @(Invoke-ScriptAnalyzer @analyzerArguments)) {
        Write-Output ('{0}:{1}: {2} {3}: {4}' -f $file, $finding.Line, $finding.Severity, $finding.RuleName, $finding.Message)
        $findings += $finding
    }
}
if ($findings.Count -gt 0) { exit 1 }
Write-Output 'No findings.'
