[CmdletBinding()]
param(
    [string]$PythonLauncher = "py",
    [string]$PythonVersion = "3.11",
    [string]$VenvDir = "",
    [string]$EnvFile = "",
    [string]$MountUser = "$env:USERDOMAIN\$env:USERNAME",
    [switch]$AllowHttpBasic
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
    Write-Host "Requesting administrator privileges..."
    $ElevationArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-PythonLauncher", "`"$PythonLauncher`"",
        "-PythonVersion", "`"$PythonVersion`"",
        "-VenvDir", "`"$VenvDir`"",
        "-EnvFile", "`"$EnvFile`"",
        "-MountUser", "`"$MountUser`""
    )
    if ($AllowHttpBasic) {
        $ElevationArgs += "-AllowHttpBasic"
    }
    $Elevated = Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $ElevationArgs -Wait -PassThru
    exit $Elevated.ExitCode
}
$PythonLauncherCommand = Get-Command $PythonLauncher -ErrorAction Stop
$PythonLauncher = $PythonLauncherCommand.Source
$ServiceName = "AnyShareUnofficialWebDAVX18765"
$TaskName = "AnyShareUnofficialWebDAVX18765Mount"

# Both the service host and a running mount task load Python DLLs from the
# isolated environment. Stop them before pip or the runtime repair replaces
# those files during an upgrade/reinstall.
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask -and $ExistingTask.State -eq "Running") {
    Write-Host "Stopping existing mount task $TaskName..."
    Stop-ScheduledTask -TaskName $TaskName
    $TaskStopDeadline = (Get-Date).AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 200
        $ExistingTask = Get-ScheduledTask -TaskName $TaskName
    } while ($ExistingTask.State -eq "Running" -and (Get-Date) -lt $TaskStopDeadline)
    if ($ExistingTask.State -eq "Running") {
        throw "Existing mount task did not stop within 15 seconds: $TaskName"
    }
}
$ExistingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($ExistingService -and $ExistingService.Status -ne "Stopped") {
    Write-Host "Stopping existing service $ServiceName to unlock its runtime..."
    Stop-Service -Name $ServiceName -Force
    $ExistingService.WaitForStatus(
        [System.ServiceProcess.ServiceControllerStatus]::Stopped,
        [TimeSpan]::FromSeconds(30)
    )
}

Write-Host "Preparing isolated Python environment..."
$Python = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $Python)) {
    & $PythonLauncher "-$PythonVersion" -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the isolated Python environment." }
}
if (-not (Test-Path $Python)) { throw "Isolated Python was not created: $Python" }
& $Python -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw "Failed to bootstrap pip in the isolated environment." }
$ProjectRequirement = "${Root}[windows-mount]"
& $Python -m pip install --disable-pip-version-check --editable $ProjectRequirement
if ($LASTEXITCODE -ne 0) { throw "Failed to install the project and Windows mount dependencies." }
$PrepareRuntimeScript = Join-Path $PSScriptRoot "prepare_service_runtime.py"
& $Python $PrepareRuntimeScript
if ($LASTEXITCODE -ne 0) { throw "Failed to prepare the isolated pywin32 service runtime." }

# The service runs as LocalSystem and cannot inherit the interactive shell environment.
[Environment]::SetEnvironmentVariable("ANYSHARE_MOUNT_ENV_FILE", $EnvFile, "Machine")

# Limit the credential file to SYSTEM, administrators, and the user that maps the drive.
& icacls $EnvFile /inheritance:r /grant:r "*S-1-5-18:(R)" "*S-1-5-32-544:(F)" "${MountUser}:(R)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to secure $EnvFile" }

$ServiceScript = Join-Path $PSScriptRoot "service.py"
& $Python $ServiceScript --startup auto install
if ($LASTEXITCODE -ne 0) {
    # Re-running the installer should update an existing service.
    & $Python $ServiceScript update --startup auto
    if ($LASTEXITCODE -ne 0) { throw "Service installation failed." }
}

Set-Service -Name "WebClient" -StartupType Manual
if ($AllowHttpBasic) {
    Write-Warning "Enabling Basic authentication over HTTP for the Windows WebClient service. Prefer trusted HTTPS."
    $WebClientParameters = "HKLM:\SYSTEM\CurrentControlSet\Services\WebClient\Parameters"
    Set-ItemProperty -Path $WebClientParameters -Name "BasicAuthLevel" -Type DWord -Value 2
    Restart-Service -Name "WebClient" -Force
} else {
    Start-Service -Name "WebClient"
}

$GatewayService = Get-Service -Name $ServiceName
if ($GatewayService.Status -eq "Running") {
    Restart-Service -Name $ServiceName
} else {
    Start-Service -Name $ServiceName
}

$MountScript = Join-Path $PSScriptRoot "mount_drive.py"
$MountLog = Join-Path $PSScriptRoot "mount_drive.log"
$ActionArgs = "`"$MountScript`" --env-file `"$EnvFile`" --force --log-file `"$MountLog`""
$Action = New-ScheduledTaskAction -Execute $Python -Argument $ActionArgs -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $MountUser
$TaskPrincipal = New-ScheduledTaskPrincipal -UserId $MountUser -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $TaskPrincipal -Settings $Settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
$MountDeadline = (Get-Date).AddSeconds(75)
do {
    Start-Sleep -Milliseconds 500
    $TaskState = (Get-ScheduledTask -TaskName $TaskName).State
} while ($TaskState -eq "Running" -and (Get-Date) -lt $MountDeadline)
$TaskResult = (Get-ScheduledTaskInfo -TaskName $TaskName).LastTaskResult
if ($TaskState -eq "Running") {
    Write-Warning "Drive mount validation did not finish within 75 seconds. See $MountLog"
} elseif ($TaskResult -ne 0) {
    Write-Warning "Drive mount failed with task result $TaskResult. See $MountLog"
} else {
    Write-Host "Drive X: was verified in the non-elevated user session."
}

Write-Host "Installed AnyShare WebDAV service and login mount task."
Write-Host "Environment: $EnvFile"
Write-Host "Isolated runtime: $VenvDir"
Write-Host "Mount user: $MountUser"
