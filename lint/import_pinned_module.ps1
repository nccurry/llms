# Dot-sourced by run_pester.ps1 and run_psscriptanalyzer.ps1.
# PowerShell adds the user, shared and built-in module folders to PSModulePath, so a copy of
# Pester or PSScriptAnalyzer installed elsewhere could be loaded instead of the pinned one. These
# functions import the version pinned in powershell-modules.json from .tools/powershell-modules
# by its exact path, and check where every loaded copy came from. The runners check again after
# the tool has run, because a script it runs (a test, for example) can import another copy.
function Get-PinnedModuleFolder {
    param([Parameter(Mandatory = $true)][string] $Name)
    $modulesRoot = Join-Path (Split-Path -Parent $PSScriptRoot) '.tools/powershell-modules'
    $pins = (Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'powershell-modules.json') | ConvertFrom-Json).modules
    $version = $pins.$Name.version
    if (-not $version) { throw "powershell-modules.json does not pin $Name." }
    return [pscustomobject] @{
        Version = $version
        Folder  = Join-Path $modulesRoot "$Name/$version"
        Root    = $modulesRoot
    }
}

# Throws unless every loaded copy of the module is the pinned version from the pinned folder.
function Assert-PinnedModule {
    param([Parameter(Mandatory = $true)][string] $Name)
    $pin = Get-PinnedModuleFolder -Name $Name
    $expected = [IO.Path]::GetFullPath($pin.Folder)
    $loaded = @(Get-Module -Name $Name)
    if ($loaded.Count -eq 0) { throw "$Name is not loaded." }
    foreach ($module in $loaded) {
        if ($module.Version -ne [version] $pin.Version -or [IO.Path]::GetFullPath($module.ModuleBase) -ne $expected) {
            throw "Loaded $Name from $($module.ModuleBase) instead of $expected."
        }
    }
}

function Import-PinnedModule {
    param([Parameter(Mandatory = $true)][string] $Name)
    $pin = Get-PinnedModuleFolder -Name $Name
    $manifest = Join-Path $pin.Folder "$Name.psd1"
    if (-not (Test-Path -LiteralPath $manifest)) {
        throw "$Name $($pin.Version) is not installed in $($pin.Root). Run task deps:dev-tools."
    }
    Import-Module -Name $manifest -Force
    Assert-PinnedModule -Name $Name
    Write-Output "$Name $($pin.Version) from $([IO.Path]::GetFullPath($pin.Folder))"
}
