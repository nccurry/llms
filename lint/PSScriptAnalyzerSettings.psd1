# Settings for lint:powershell. The scripts run on Windows PowerShell 5.1, so the
# 5.1 syntax and command rules are switched on; they are off by default.
@{
    Severity     = @('Error', 'Warning')
    IncludeRules = @('*')
    Rules        = @{
        PSUseCompatibleSyntax   = @{
            Enable         = $true
            TargetVersions = @('5.1')
        }
        PSUseCompatibleCommands = @{
            Enable         = $true
            # Windows 10 Pro (build 17763) with Windows PowerShell 5.1, from PSScriptAnalyzer's own profiles.
            TargetProfiles = @('win-48_x64_10.0.17763.0_5.1.17763.316_x64_4.0.30319.42000_framework')
        }
    }
}
