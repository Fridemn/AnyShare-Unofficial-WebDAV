[CmdletBinding()]
param(
    [string]$VenvDir = "",
    [string]$EnvFile = "",
    [string]$MountUser = "$env:USERDOMAIN\$env:USERNAME",
    [switch]$KeepVenv
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $EnvFile) {
    $EnvFile = Join-Path $Root ".env"
}
$EnvFile = (Resolve-Path $EnvFile).Path
if (-not $VenvDir) {
    $VenvDir = Join-Path $Root ".venv-windows-mount"
}
$VenvDir = [IO.Path]::GetFullPath($VenvDir)

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this uninstaller from an elevated PowerShell window."
}
$Python = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Isolated Python was not found: $Python" }

$TaskName = "AnyShareUnofficialWebDAVX18765Mount"
$MountScript = Join-Path $PSScriptRoot "mount_drive.py"
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    # Run unmount in the interactive user's task context before removing persistence.
    $ActionArgs = "`"$MountScript`" --env-file `"$EnvFile`" --unmount --force"
    $Action = New-ScheduledTaskAction -Execute $Python -Argument $ActionArgs -WorkingDirectory $Root
    $Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5)
    $TaskPrincipal = New-ScheduledTaskPrincipal -UserId $MountUser -LogonType Interactive -RunLevel Limited
    Set-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $TaskPrincipal | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 3
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$ServiceScript = Join-Path $PSScriptRoot "service.py"
& $Python $ServiceScript stop 2>$null
& $Python $ServiceScript remove
[Environment]::SetEnvironmentVariable("ANYSHARE_MOUNT_ENV_FILE", $null, "Machine")
if (-not $KeepVenv) {
    Remove-Item -LiteralPath $VenvDir -Recurse -Force
}

Write-Host "Removed AnyShare WebDAV service and login mount task."
