$ErrorActionPreference = 'Stop'
$originalSetup = [IO.Path]::GetFullPath($env:QR_INSTALLER)
$root = Join-Path $env:LOCALAPPDATA 'QR-Album'
$installedSetup = Join-Path $root 'QR_Setup.cmd'
$releaseNumber = __RELEASE_NUMBER__
$selected = $originalSetup
$stage = $null
$feed = 'https://raw.githubusercontent.com/furc0/QR/main/installer/release.json'

function Publish-Setup($sourcePath, $destination) {
    if ($sourcePath -eq $destination) { return }
    if ([IO.File]::Exists($destination) -and
        (Get-FileHash -LiteralPath $sourcePath).Hash -eq (Get-FileHash -LiteralPath $destination).Hash) { return }
    $tmp = Join-Path ([IO.Path]::GetDirectoryName($destination)) ([guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::Copy($sourcePath,$tmp)
        if ([IO.File]::Exists($destination)) { [IO.File]::Replace($tmp,$destination,[System.Management.Automation.Language.NullString]::Value) }
        else { [IO.File]::Move($tmp,$destination) }
    } finally { if ([IO.File]::Exists($tmp)) { [IO.File]::Delete($tmp) } }
}

function Read-BuildNumber($path) {
    $match = [regex]::Match([IO.File]::ReadAllText($path),'(?m)^rem QR_BUILD ([0-9]+)\r?$')
    if (-not $match.Success) { throw 'Invalid QR installer build number.' }
    return [long]$match.Groups[1].Value
}

$mutex = New-Object Threading.Mutex($false,'Local\QRAlbumInstaller')
try { $locked = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $locked = $true }
if (-not $locked) { Write-Host 'QR is already running. Close its server window before updating.'; exit 1 }
try {
    [IO.Directory]::CreateDirectory($root) | Out-Null
    if ([IO.File]::Exists($installedSetup)) {
        $installedNumber = Read-BuildNumber $installedSetup
        if ($installedNumber -gt $releaseNumber) {
            $selected = $installedSetup
            $releaseNumber = $installedNumber
        }
    }
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $request = @{UseBasicParsing=$true; TimeoutSec=8; ErrorAction='Stop'; Headers=@{'Cache-Control'='no-cache'}}
        $release = (Invoke-WebRequest @request -Uri $feed).Content | ConvertFrom-Json
        if ([long]$release.version -gt $releaseNumber) {
            if ($release.sha256 -notmatch '^[0-9a-f]{64}$' -or $release.blob -notmatch '^[0-9a-f]{40}$') { throw 'Invalid QR update manifest.' }
            $stage = Join-Path $root ([guid]::NewGuid().ToString('N') + '.cmd')
            # Use an immutable Git blob so a new commit during download cannot mix releases.
            $uri = 'https://api.github.com/repos/furc0/QR/git/blobs/' + $release.blob
            $request.TimeoutSec = 25
            $reply = (Invoke-WebRequest @request -Uri $uri).Content | ConvertFrom-Json
            if ($reply.encoding -ne 'base64' -or $reply.sha -ne $release.blob) { throw 'Unexpected GitHub response.' }
            [IO.File]::WriteAllBytes($stage,[Convert]::FromBase64String($reply.content))
            if ((Get-FileHash -LiteralPath $stage).Hash -ne $release.sha256 -or (Read-BuildNumber $stage) -ne $release.version) { throw 'QR update verification failed.' }
            $selected = $stage
            Write-Host "Installing QR update $($release.version)..."
        }
    } catch { Write-Warning ("GitHub update unavailable. Using the local installer. " + $_.Exception.Message) }

    $env:QR_INSTALLER = $selected
    $text = [IO.File]::ReadAllText($selected)
    $body = (($text -split '(?m)^# QR_INSTALL_BODY\r?$')[1] -split '(?m)^:QR_PAYLOAD\r?$')[0]
    if (-not $body) { throw 'QR installation code is missing.' }
    & ([ScriptBlock]::Create($body))
} finally {
    if ($stage -and [IO.File]::Exists($stage)) { [IO.File]::Delete($stage) }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
