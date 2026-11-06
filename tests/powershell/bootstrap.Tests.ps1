# Pester tests for the functions in bootstrap.ps1. Run with the test:powershell task.
# Nothing here downloads or installs: bootstrap.ps1 is dot-sourced, which loads its
# functions without running the bootstrap.

BeforeDiscovery {
    $script:onWindows = $env:OS -eq 'Windows_NT'
    $script:platforms = @('linux-x64', 'linux-arm64', 'macos-x64', 'macos-arm64', 'windows-x64', 'windows-arm64')
}

BeforeAll {
    $script:bootstrap = Join-Path $PSScriptRoot '../../bootstrap.ps1'
    . $script:bootstrap

    $script:platforms = @('linux-x64', 'linux-arm64', 'macos-x64', 'macos-arm64', 'windows-x64', 'windows-arm64')
    # One distinct 64-character value per platform, so a lookup of the wrong key is noticed.
    $script:sampleChecksums = @{}
    $position = 0
    foreach ($name in $script:platforms) {
        $script:sampleChecksums[$name] = ([string] $position) * 64
        $position++
    }
    $lines = @('[vars]', 'mise_version = "2026.10.3"')
    foreach ($name in $script:platforms) {
        $lines += 'mise_sha256_{0} = "{1}"' -f ($name -replace '-', '_'), $script:sampleChecksums[$name]
    }
    $script:sampleConfiguration = $lines -join "`n"
}

Describe 'Get-PinnedMiseChecksum' {
    It 'returns the pinned value for <_>' -ForEach $platforms {
        Get-PinnedMiseChecksum -Configuration $script:sampleConfiguration -Platform $_ |
            Should -Be $script:sampleChecksums[$_]
    }

    It 'reads a configuration with CRLF line endings' {
        $crlf = $script:sampleConfiguration -replace "`n", "`r`n"
        Get-PinnedMiseChecksum -Configuration $crlf -Platform 'windows-x64' |
            Should -Be $script:sampleChecksums['windows-x64']
    }

    It 'throws a message naming the missing key' {
        $without = ($script:sampleConfiguration -split "`n" | Where-Object { $_ -notmatch 'windows_arm64' }) -join "`n"
        { Get-PinnedMiseChecksum -Configuration $without -Platform 'windows-arm64' } |
            Should -Throw -ExpectedMessage '*mise_sha256_windows_arm64*'
    }

    It 'rejects a value that is not 64 lowercase hex characters' {
        $short = $script:sampleConfiguration -replace '(mise_sha256_linux_x64 = ")0+', '${1}abc'
        { Get-PinnedMiseChecksum -Configuration $short -Platform 'linux-x64' } |
            Should -Throw -ExpectedMessage '*mise_sha256_linux_x64*'
    }

    It 'finds every platform in the repository mise.toml' {
        $configuration = [IO.File]::ReadAllText((Join-Path $PSScriptRoot '../../mise.toml'))
        foreach ($name in $script:platforms) {
            Get-PinnedMiseChecksum -Configuration $configuration -Platform $name | Should -Match '^[0-9a-f]{64}$'
        }
    }
}

Describe 'Get-PinnedMiseVersion' {
    It 'returns the pinned version' {
        Get-PinnedMiseVersion -Configuration $script:sampleConfiguration | Should -Be '2026.10.3'
    }

    It 'throws when the version is missing' {
        { Get-PinnedMiseVersion -Configuration '[vars]' } | Should -Throw -ExpectedMessage '*mise_version*'
    }
}

Describe 'task.cmd text' {
    It 'calls PowerShell through %SystemRoot%' {
        $text = Get-TaskCommandText
        $text | Should -Match ([regex]::Escape('set "LLMS_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"'))
        $text | Should -Not -Match '(?m)^\s*"?powershell(\.exe)?"?\s'
    }

    It 'uses CRLF on every line' {
        $text = Get-TaskCommandText
        $text | Should -Not -Match "(?<!`r)`n"
        $text | Should -Match "`r`n$"
    }

    It 'uses CRLF when the script file itself has <name> line endings' -ForEach @(
        @{ name = 'LF'; newline = "`n" }
        @{ name = 'CRLF'; newline = "`r`n" }
    ) {
        $source = ([IO.File]::ReadAllText($script:bootstrap) -replace "`r?`n", $newline)
        $copy = Join-Path $TestDrive "bootstrap-$name.ps1"
        [IO.File]::WriteAllText($copy, $source)
        $text = & {
            . $copy
            Get-TaskCommandText
        }
        $text | Should -Be (Get-TaskCommandText)
        $text | Should -Not -Match "(?<!`r)`n"
    }
}

Describe 'Write-TaskCommand' {
    BeforeEach {
        $script:path = Join-Path $TestDrive 'task.cmd'
        Remove-Item -LiteralPath $script:path -ErrorAction SilentlyContinue
    }

    It 'writes a missing file with CRLF endings and no byte order mark' {
        Write-TaskCommand -Path $script:path | Should -BeTrue
        $bytes = [IO.File]::ReadAllBytes($script:path)
        [Text.Encoding]::ASCII.GetString($bytes) | Should -Be (Get-TaskCommandText)
        $bytes[0] | Should -Be ([byte][char] '@')
    }

    It 'does not rewrite a file that has the same text and different line endings' {
        $lfText = (Get-TaskCommandText) -replace "`r`n", "`n"
        [IO.File]::WriteAllText($script:path, $lfText)
        Write-TaskCommand -Path $script:path | Should -BeFalse
        [IO.File]::ReadAllText($script:path) | Should -Be $lfText
    }

    It 'does not rewrite a file that is already current' {
        Write-TaskCommand -Path $script:path | Out-Null
        Write-TaskCommand -Path $script:path | Should -BeFalse
    }

    It 'rewrites a file whose text differs' {
        [IO.File]::WriteAllText($script:path, "@echo off`r`necho old`r`n")
        Write-TaskCommand -Path $script:path | Should -BeTrue
        [IO.File]::ReadAllText($script:path) | Should -Be (Get-TaskCommandText)
    }
}

Describe 'Running bootstrap.ps1' {
    It 'loads its functions without running the bootstrap when dot-sourced' {
        # Run directly on Linux, the bootstrap stops with an error at its Windows check.
        { . $script:bootstrap } | Should -Not -Throw
        Get-Command Invoke-Bootstrap -CommandType Function | Should -Not -BeNullOrEmpty
    }

    # On Linux the bootstrap's first check refuses to continue, before it downloads anything.
    It 'runs the bootstrap when executed directly' -Skip:$script:onWindows {
        $pwsh = (Get-Process -Id $PID).Path
        $output = & $pwsh -NoProfile -File $script:bootstrap 2>&1 | Out-String
        $LASTEXITCODE | Should -Not -Be 0
        $output | Should -Match 'Use bootstrap\.sh on Linux/macOS'
    }
}
