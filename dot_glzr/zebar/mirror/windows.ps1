param(
    [ValidateSet('kanata', 'network', 'bluetooth', 'weather', 'battery')][string]$Query,
    [ValidateSet('toggle-kanata')][string]$Action
)
$hasQuery = $PSBoundParameters.ContainsKey('Query')
$hasAction = $PSBoundParameters.ContainsKey('Action')
if ($hasQuery -eq $hasAction) { throw 'Specify exactly one query or action' }
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Get-BluetoothDevices {
    # Query connected association endpoints, not merely paired/present PnP nodes.
    # Protocol IDs: https://learn.microsoft.com/windows/uwp/devices-sensors/aep-service-class-ids
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType = WindowsRuntime]
    $null = [Windows.Devices.Enumeration.DeviceInformationCollection, Windows.Devices.Enumeration, ContentType = WindowsRuntime]
    $null = [Windows.Devices.Enumeration.DeviceInformationKind, Windows.Devices.Enumeration, ContentType = WindowsRuntime]
    $selector = '(System.Devices.Aep.ProtocolId:="{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}" OR System.Devices.Aep.ProtocolId:="{bb7bb05e-5972-42b5-94fc-76eaa7084d49}") AND System.Devices.Aep.IsConnected:=System.StructuredQueryType.Boolean#True'
    $operation = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync(
        $selector, [string[]]@('System.Devices.Aep.ContainerId'),
        [Windows.Devices.Enumeration.DeviceInformationKind]::AssociationEndpoint)
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
        $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $task = $asTask.MakeGenericMethod([Windows.Devices.Enumeration.DeviceInformationCollection]).Invoke($null, @($operation))
    if (-not $task.Wait(8000)) { throw 'Bluetooth enumeration timed out' }

    # Battery is driver-dependent. Match by container ID, never by friendly name.
    $batteries = @{}
    foreach ($device in @(Get-PnpDevice -Class Bluetooth -PresentOnly -ErrorAction SilentlyContinue)) {
        $properties = @(Get-PnpDeviceProperty -InstanceId $device.InstanceId -ErrorAction SilentlyContinue)
        $container = ($properties | Where-Object KeyName -eq 'DEVPKEY_Device_ContainerId' | Select-Object -First 1).Data
        $battery = ($properties | Where-Object KeyName -eq '{104ea319-6ee2-4701-bd47-8ddbf425bbE5} 2' | Select-Object -First 1).Data
        if ($null -ne $container -and $null -ne $battery -and $battery -ge 0 -and $battery -le 100) {
            $batteries[$container.ToString()] = [int]$battery
        }
    }
    $seen = @{}
    foreach ($device in $task.Result) {
        $container = [string]$device.Properties['System.Devices.Aep.ContainerId']
        $key = if ($container) { $container } else { $device.Id }
        if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            [pscustomobject]@{ name = $device.Name; battery = $batteries[$container] }
        }
    }
}

function Get-KanataProcesses {
    @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'kanata*' })
}

function Find-Kanata {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($userPath) { $env:Path = "$env:Path;$userPath" }
    $command = Get-Command -Name 'kanata*.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) { throw 'No Kanata executable was found in the user PATH' }
    $command.Path
}

try {
    if ($Action -eq 'toggle-kanata') {
        $process = Get-KanataProcesses
        if ($process) {
            $process | Stop-Process -Force
            $result = $false
        } else {
            Start-Process -FilePath (Find-Kanata) -ArgumentList @('--cfg', (Join-Path $HOME '.config\kanata\kanata.kbd'))
            $result = $true
        }
    } else {
        $result = switch ($Query) {
        'kanata' { [bool](Get-KanataProcesses) }
        'battery' {
            # Uses Windows GetSystemPowerStatus, independent of Zebar's battery driver query.
            Add-Type -AssemblyName System.Windows.Forms
            $power = [System.Windows.Forms.SystemInformation]::PowerStatus
            $flags = [int]$power.BatteryChargeStatus
            if ($flags -eq 255) { throw 'Windows battery status is unknown' }
            if ($flags -band 128) {
                [pscustomobject]@{ present = $false }
            } else {
                $fraction = [double]$power.BatteryLifePercent
                $charging = [bool]($flags -band 8)
                $status = if ($charging) { 'Charging' } elseif ($power.PowerLineStatus -eq 'Online') {
                    'Plugged in (not charging)'
                } else { 'Discharging' }
                [pscustomobject]@{
                    present = $true
                    chargePercent = $(if ($fraction -ge 0 -and $fraction -le 1) { [math]::Round($fraction * 100) } else { $null })
                    isCharging = $charging
                    state = $status
                }
            }
        }
        'weather' {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-RestMethod -Uri 'https://wttr.in/?format=j1' -UserAgent 'waybar-weather/1.0' -TimeoutSec 8
        }
        'bluetooth' { ,@(Get-BluetoothDevices) }
        'network' {
            $profile = Get-NetConnectionProfile -ErrorAction SilentlyContinue |
                Where-Object { $_.IPv4Connectivity -ne 'Disconnected' } | Select-Object -First 1
            $adapter = if ($profile) {
                Get-NetAdapter -InterfaceIndex $profile.InterfaceIndex -ErrorAction SilentlyContinue
            } else {
                $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                    Where-Object State -eq 'Alive' | Sort-Object RouteMetric | Select-Object -First 1
                if ($route) { Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue }
            }
            if ($adapter -and $adapter.Status -eq 'Up') {
                $stats = $adapter | Get-NetAdapterStatistics
                [pscustomobject]@{
                    interfaceId = [string]$adapter.InterfaceGuid
                    name = if ($profile.Name) { $profile.Name } else { $adapter.Name }
                    receivedBytes = [double]$stats.ReceivedBytes
                    timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
                }
            } else { $null }
        }
        }
    }
    ConvertTo-Json -InputObject $result -Depth 12 -Compress
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
