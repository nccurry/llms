param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$CopyFrom
)

$ErrorActionPreference = 'Stop'
$env:PSModulePath = "$PSHOME/Modules;$env:PSModulePath"
if ($CopyFrom) {
    $permissions = Get-Acl -LiteralPath $CopyFrom
} else {
    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) {
        $permissions = New-Object System.Security.AccessControl.DirectorySecurity
        $inheritance = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    } else {
        $permissions = New-Object System.Security.AccessControl.FileSecurity
        $inheritance = [System.Security.AccessControl.InheritanceFlags]::None
    }
    $permissions.SetAccessRuleProtection($true, $false)
    $account = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    foreach ($principal in @($account, (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')))) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $principal, 'FullControl', $inheritance, 'None', 'Allow'
        )
        $permissions.AddAccessRule($rule)
    }
}
# Set only the DACL. Set-Acl on a newly constructed descriptor can request
# audit/owner privileges that an ordinary user does not possess.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class LlmsFilePermissions {
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetFileSecurity(string path, uint information, byte[] descriptor);
}
'@
$information = if ($permissions.AreAccessRulesProtected) { [uint32]2147483652 } else { [uint32]536870916 }
if (-not [LlmsFilePermissions]::SetFileSecurity($Path, $information, $permissions.GetSecurityDescriptorBinaryForm())) {
    throw (New-Object ComponentModel.Win32Exception([Runtime.InteropServices.Marshal]::GetLastWin32Error()))
}
