$ErrorActionPreference = 'Stop'
$expected = '__SHA256__'
$root = Join-Path $env:LOCALAPPDATA 'QR-Album'
$stateFile = Join-Path $root 'installation.json'
$env:PYTHONDONTWRITEBYTECODE = '1'

function Find-DataDirectory {
    if ($env:QR_DATA_DIR) { return [IO.Path]::GetFullPath($env:QR_DATA_DIR) }
    $found = @()
    $near = Split-Path -Parent $originalSetup
    foreach ($folder in @($near, (Join-Path $root 'data'))) {
        foreach ($file in @('data\qr.sqlite3', 'qr.sqlite3')) {
            $candidate = Join-Path $folder $file
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { $found += (Get-Item -LiteralPath $candidate).DirectoryName }
        }
    }
    $folders = New-Object 'System.Collections.Generic.Stack[string]'
    if (Test-Path -LiteralPath 'C:\QR_ALBUM') { $folders.Push('C:\QR_ALBUM') }
    while ($folders.Count) {
        $folder = $folders.Pop()
        foreach ($entry in Get-ChildItem -LiteralPath $folder -Force) {
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            if ($entry.PSIsContainer) {
                if ($entry.Name -notin '.git','.venv','node_modules','__pycache__','files','models') { $folders.Push($entry.FullName) }
            } elseif ($entry.Name -eq 'qr.sqlite3') { $found += $entry.DirectoryName }
        }
    }
    $found = @($found | Sort-Object -Unique)
    if ($found.Count -eq 1) { return $found[0] }
    if ($found.Count -gt 1) {
        Write-Host 'Multiple QR databases found. Select the one you want to open:'
        for ($i=0; $i -lt $found.Count; $i++) { Write-Host ("{0}. {1}" -f ($i+1),$found[$i]) }
        $selection = 0
        if (-not [int]::TryParse((Read-Host 'Number'),[ref]$selection) -or $selection -lt 1 -or $selection -gt $found.Count) { throw 'No database selected.' }
        return $found[$selection-1]
    }
    return Join-Path $root 'data'
}

function Save-State($state) {
    $temp = Join-Path $root ([guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($temp, ($state | ConvertTo-Json))
        if ([IO.File]::Exists($stateFile)) { [IO.File]::Replace($temp,$stateFile,[System.Management.Automation.Language.NullString]::Value) }
        else { [IO.File]::Move($temp,$stateFile) }
    } finally { if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) } }
}

function Test-Runtime($folder) {
    $exe = Join-Path $folder '.venv\Scripts\python.exe'
    if (-not [IO.File]::Exists($exe)) { return $false }
    try {
        & $exe -c "import fastapi, uvicorn, python_multipart" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

[IO.Directory]::CreateDirectory($root) | Out-Null
$old = $null
$current = $null
if ([IO.File]::Exists($stateFile)) {
    $old = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($old.release -notmatch '^release-[0-9a-f]{32}$' -or -not [IO.Path]::IsPathRooted($old.data)) { throw 'Invalid QR installation settings.' }
    $current = Join-Path $root $old.release
    $env:QR_DATA_DIR = $old.data
    if (-not [IO.File]::Exists((Join-Path $env:QR_DATA_DIR 'qr.sqlite3'))) { throw "Saved database is unavailable: $env:QR_DATA_DIR" }
} else { $env:QR_DATA_DIR = Find-DataDirectory }
Write-Host "QR data: $env:QR_DATA_DIR"
if (-not $old -or $old.package -ne $expected -or -not (Test-Runtime $current)) {
    $release = 'release-' + [guid]::NewGuid().ToString('N')
    $folder = Join-Path $root $release
    $zip = Join-Path $env:TEMP ('qr-' + [guid]::NewGuid().ToString('N') + '.zip')
    $committed = $false
    try {
        $source = [IO.File]::ReadAllText($env:QR_INSTALLER)
        $encoded = ($source -split '(?m)^:QR_PAYLOAD\r?$')[-1]
        [IO.File]::WriteAllBytes($zip,[Convert]::FromBase64String($encoded))
        if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $expected) { throw 'QR archive checksum mismatch. Download the installer again.' }
        Expand-Archive -LiteralPath $zip -DestinationPath $folder
        Push-Location
        try { & (Join-Path $folder 'run_qr.ps1') -PrepareOnly } finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw 'Could not prepare QR dependencies.' }
        $env:PYTHONPATH = Join-Path $folder 'server'
        $python = Join-Path $folder '.venv\Scripts\python.exe'
        & $python -c "from qr_server.main import setup_status; setup_status()"
        if ($LASTEXITCODE -ne 0) { throw 'QR could not open the catalogue.' }
        & $python (Join-Path $folder 'installer\inventory.py') record $folder
        if ($LASTEXITCODE -ne 0) { throw 'Could not record installed files.' }
        Save-State @{release=$release; package=$expected; data=$env:QR_DATA_DIR}
        $committed = $true
    } catch {
        if (-not $old -or -not (Test-Runtime $current)) { throw }
        Write-Warning ("Update failed. Starting the previous installation. " + $_.Exception.Message)
    } finally {
        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
        if (-not $committed -and [IO.Directory]::Exists($folder)) { Remove-Item -LiteralPath $folder -Recurse -Force }
    }
    if ($committed) { $current = $folder }
}
if ($null -eq $committed -or $committed) {
    Publish-Setup $env:QR_INSTALLER $installedSetup
} elseif (-not [IO.File]::Exists($installedSetup)) {
    # First upgrade from a legacy release failed. Keep its existing shortcut.
    $installedSetup = Join-Path $current 'QR_Setup.cmd'
}
# A release directory belongs to the inventory cleaner. External downloaded
# installers may be on read-only media; the installed launcher still updates.
if (($null -eq $committed -or $committed) -and $originalSetup -ne $installedSetup -and (Split-Path -Parent $originalSetup) -notlike "$root\release-*") {
    try { Publish-Setup $installedSetup $originalSetup }
    catch { Write-Warning "Cannot refresh $originalSetup. Use the QR Album desktop shortcut." }
}
$shortcutPath = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'QR Album.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
if (-not (Test-Path -LiteralPath $shortcutPath) -or $shortcut.TargetPath -eq $installedSetup -or $shortcut.TargetPath -like "$root\release-*\QR_Setup.cmd") {
    $shortcut.TargetPath = $installedSetup
    $shortcut.WorkingDirectory = $current
    $shortcut.Save()
}
$python = Join-Path $current '.venv\Scripts\python.exe'
Set-Location -LiteralPath $current
if ($old -and $current -ne (Join-Path $root $old.release)) {
    $previous = Join-Path $root $old.release
    if ([IO.Directory]::Exists($previous)) {
        & $python (Join-Path $current 'installer\inventory.py') clean $previous
        if ($LASTEXITCODE -ne 0) { Write-Warning "Could not clean previous release: $previous" }
    }
}
$env:PYTHONPATH = Join-Path $current 'server'
if ($stage -and [IO.File]::Exists($stage)) { [IO.File]::Delete($stage) }
& $python -m qr_server.launcher --open-browser
exit $LASTEXITCODE
