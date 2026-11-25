# Open Plannotator sessions in a Herdr app pane instead of a browser.
# Windows port of bin/plannotator-herdr from github.com/iuliansafta/herdr-plannotator.
#
#   plannotator-herdr <http://...>        browser mode: Plannotator runs this as
#                                         PLANNOTATOR_BROWSER; it opens the pane
#                                         and returns at once.
#   plannotator-herdr <plannotator args>  wrapper mode: runs plannotator with
#                                         this launcher as its browser.
#
# PLANNOTATOR_HERDR_PLACE: right (default), down, or tab.

$ErrorActionPreference = 'Stop'
$shim = Join-Path $PSScriptRoot 'plannotator-herdr.cmd'
$first = if ($args.Count -gt 0) { [string]$args[0] } else { '' }

# The installer adds plannotator to the user PATH, which shells started before
# the install don't have yet.
$plannotator = (Get-Command plannotator -ErrorAction SilentlyContinue).Source
if (-not $plannotator) { $plannotator = Join-Path $env:LOCALAPPDATA 'plannotator\plannotator.exe' }

if ($first -notmatch '^https?://') {
    $env:PLANNOTATOR_BROWSER = $shim
    & $plannotator @args
    exit $LASTEXITCODE
}

$url = $first

function Open-Fallback([string]$why) {
    [Console]::Error.WriteLine("plannotator-herdr: $why; opening the browser instead")
    Start-Process $url
    exit 0
}

# Arguments reach herdr-app as one raw command line, so JSON arguments are
# escaped by hand (compact JSON of a localhost URL has no spaces).
function Quote-Json([string]$json) { $json -replace '"', '\"' }

# herdr-app is a GUI-subsystem program: PowerShell neither waits for it nor
# sets $LASTEXITCODE when it is called directly, so wait for it explicitly.
function Invoke-Herdr([string[]]$argv) {
    $out = [IO.Path]::GetTempFileName()
    try {
        $p = Start-Process herdr-app -ArgumentList $argv -NoNewWindow -Wait -PassThru -RedirectStandardOutput $out
        return $p.ExitCode
    } finally {
        Remove-Item $out -ErrorAction SilentlyContinue
    }
}

if (-not (Get-Command herdr-app -ErrorAction SilentlyContinue)) { Open-Fallback 'herdr-app not found' }
if ((Invoke-Herdr @('status')) -ne 0) { Open-Fallback 'no herdr window' }

$props = @{ url = $url }
try {
    $v = ((& $plannotator --version 2>$null) -split '\s+')[1]
    if ($v) { $props.version = $v }
} catch {}
$propsJson = Quote-Json (ConvertTo-Json $props -Compress)

$place = if ($env:PLANNOTATOR_HERDR_PLACE) { $env:PLANNOTATOR_HERDR_PLACE } else { 'right' }

# The pane and space of the terminal that started plannotator (the agent's),
# when it is one of this computer's terminals in the window.
$pane = $null
$space = $null
if ($env:HC_TERMINAL_ID) {
    try {
        $ls = (herdr-app ls | Out-String) | ConvertFrom-Json
        foreach ($s in $ls.spaces) {
            if ($null -ne $s.machine) { continue }
            foreach ($t in $s.tabs) {
                foreach ($term in $t.terminals) {
                    if ($term.terminal -eq $env:HC_TERMINAL_ID) { $pane = $term.pane; $space = $s.id; break }
                }
                if ($pane) { break }
            }
            if ($pane) { break }
        }
    } catch {}
}

if ($pane -and $place -ne 'tab') {
    if ((Invoke-Herdr @('do', 'pane.split', '--direction', $place, '--pane', $pane, '--mod', 'plannotator', '--props', $propsJson)) -eq 0) { exit 0 }
}

$tabArgs = @('do', 'tab.new')
if ($space) { $tabArgs += @('--space', $space) }
$tabArgs += @('--name', 'Plannotator', '--mod', 'plannotator', '--props', $propsJson)
if ((Invoke-Herdr $tabArgs) -eq 0) { exit 0 }

Open-Fallback 'herdr-app could not open the pane'
