# Dot-sourced by run_pester.ps1 and run_psscriptanalyzer.ps1.
# PowerShell adds the user, shared and built-in module folders to PSModulePath, so a copy of
# Pester or PSScriptAnalyzer installed elsewhere could be loaded instead of the pinned one. This
# imports the version pinned in powershell-modules.json from .tools/powershell-modules by its
# exact path, then checks that the loaded module really came from there.
function Import-PinnedModule {
    param([Parameter(Mandatory = $true)][string] $Name)
    $modulesRoot = Join-Path (Split-Path -Parent $PSScriptRoot) '.tools/powershell-modules'
    $pins = (Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'powershell-modules.json') | ConvertFrom-Json).modules
    $version = $pins.$Name.version
    if (-not $version) { throw "powershell-modules.json does not pin $Name." }
    $folder = Join-Path $modulesRoot "$Name/$version"
    $manifest = Join-Path $folder "$Name.psd1"
    if (-not (Test-Path -LiteralPath $manifest)) {
        throw "$Name $version is not installed in $modulesRoot. Run task deps:dev-tools."
    }
    Import-Module -Name $manifest -Force
    $expected = [IO.Path]::GetFullPath($folder)
    foreach ($module in @(Get-Module -Name $Name)) {
        if ($module.Version -ne [version] $version -or [IO.Path]::GetFullPath($module.ModuleBase) -ne $expected) {
            throw "Loaded $Name from $($module.ModuleBase) instead of $expected."
        }
    }
    Write-Output "$Name $version from $expected"
}
