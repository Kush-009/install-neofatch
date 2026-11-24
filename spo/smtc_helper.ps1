# JSON-lines bridge to the Windows media session (SMTC).
# Spawned by windows_controller.py: one JSON request per line in, one JSON reply per line out.

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Write-Reply($payload) {
    [Console]::Out.WriteLine(($payload | ConvertTo-Json -Compress -Depth 6))
    [Console]::Out.Flush()
}

function Fail($message) {
    Write-Reply @{ ok = $false; error = [string]$message }
}

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $managerType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime]
    $propsType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties, Windows.Media.Control, ContentType = WindowsRuntime]
} catch {
    Fail "Windows media session API unavailable: $($_.Exception.Message)"
    exit 1
}

$asTaskMethod = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

if ($null -eq $asTaskMethod) {
    Fail 'Could not bind the WinRT async helper.'
    exit 1
}

function Await($operation, [Type]$resultType) {
    $task = $asTaskMethod.MakeGenericMethod($resultType).Invoke($null, @($operation))
    if (-not $task.Wait(8000)) { throw 'WinRT call timed out.' }
    return $task.Result
}

try {
    $manager = Await ($managerType::RequestAsync()) $managerType
} catch {
    Fail "Could not open the media session manager: $($_.Exception.Message)"
    exit 1
}

function Get-Session {
    if ($null -eq $manager) { return $null }
    foreach ($session in @($manager.GetSessions())) {
        if ($session.SourceAppUserModelId -match 'spotify') { return $session }
    }
    return $null
}

function Get-State {
    $session = Get-Session
    if ($null -eq $session) { return @{ ok = $true; active = $false } }

    $playing = $false
    $info = $session.GetPlaybackInfo()
    $playing = ([int]$info.PlaybackStatus -eq 4)

    $title = ''; $artist = ''; $album = ''
    try {
        $props = Await ($session.TryGetMediaPropertiesAsync()) $propsType
        if ($null -ne $props) {
            $title = [string]$props.Title
            $artist = [string]$props.Artist
            $album = [string]$props.AlbumTitle
        }
    } catch {}

    $durationMs = 0; $positionMs = 0
    try {
        $timeline = $session.GetTimelineProperties()
        if ($null -ne $timeline) {
            $durationMs = [long][Math]::Round($timeline.EndTime.TotalMilliseconds)
            $positionMs = [long][Math]::Round($timeline.Position.TotalMilliseconds)
            # SMTC only refreshes Position on state changes; extrapolate from
            # LastUpdatedTime so the deck's clock matches the Spotify client.
            if ($playing) {
                $drift = ([DateTimeOffset]::UtcNow - $timeline.LastUpdatedTime).TotalMilliseconds
                if ($drift -gt 0 -and $drift -lt 3600000) {
                    $positionMs += [long][Math]::Round($drift)
                }
            }
            if ($durationMs -gt 0 -and $positionMs -gt $durationMs) { $positionMs = $durationMs }
            if ($positionMs -lt 0) { $positionMs = 0 }
        }
    } catch {}

    return @{
        ok = $true
        active = $true
        playing = $playing
        title = $title
        artist = $artist
        album = $album
        duration_ms = $durationMs
        position_ms = $positionMs
        shuffle = [bool]$info.IsShuffleActive
        shuffle_supported = [bool]$info.Controls.IsShuffleEnabled
        repeat = $(switch ([string]$info.AutoRepeatMode) { 'Track' { 'track' }; 'List' { 'context' }; default { 'off' } })
        repeat_supported = [bool]$info.Controls.IsRepeatEnabled
        seek_supported = [bool]$info.Controls.IsPlaybackPositionEnabled
        app = [string]$session.SourceAppUserModelId
    }
}

function Invoke-SessionAction([string]$action, [long]$seekMs) {
    $session = Get-Session
    if ($null -eq $session) {
        return @{ ok = $false; error = 'Spotify is not running or has no active media session.' }
    }

    try {
        switch ($action) {
            'play'   { $op = $session.TryPlayAsync() }
            'pause'  { $op = $session.TryPauseAsync() }
            'toggle' { $op = $session.TryTogglePlayPauseAsync() }
            'next'   { $op = $session.TrySkipNextAsync() }
            'prev'   { $op = $session.TrySkipPreviousAsync() }
            'seek'   { $op = $session.TryChangePlaybackPositionAsync([long]($seekMs * 10000)) }
            'shuffle' { $op = $session.TryChangeShuffleActiveAsync([bool]$seekMs) }
            'repeat' { $op = $session.TryChangeAutoRepeatModeAsync([Windows.Media.MediaPlaybackAutoRepeatMode]$seekMs) }
            default  { return @{ ok = $false; error = "Unknown action '$action'." } }
        }
        return @{ ok = [bool](Await $op ([bool])) }
    } catch {
        return @{ ok = $false; error = $_.Exception.Message }
    }
}

while ($true) {
    $line = [Console]::In.ReadLine()
    if ($null -eq $line) { break }
    $line = $line.Trim()
    if ($line -eq '') { continue }

    try {
        $cmd = $line | ConvertFrom-Json
        if ($cmd.op -eq 'quit') { break }
        switch ($cmd.op) {
            'ping'  { Write-Reply @{ ok = $true } }
            'state' { Write-Reply (Get-State) }
            default { Write-Reply (Invoke-SessionAction $cmd.op ([long]$cmd.ms)) }
        }
    } catch {
        Fail $_.Exception.Message
    }
}

exit 0
