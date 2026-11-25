param([switch]$PrepareOnly)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

function Find-Python {
    $candidates = @()
    foreach ($name in 'py.exe', 'python.exe') {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue
        if ($command -and $command.Source -notlike '*\WindowsApps\python.exe') {
            $candidates += $command.Source
        }
    }
    $candidates += Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        $options = @()
        if ((Split-Path -Leaf $candidate) -eq 'py.exe') { $options = @('-3') }
        try {
            $path = & $candidate @options -c "import sys; assert sys.version_info >= (3,11); print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $path) { return $path }
        } catch { continue }
    }
}

$usable = $false
if (Test-Path -LiteralPath $VenvPython) {
    try {
        & $VenvPython -c "import sys, pip; assert sys.version_info >= (3,11)" 2>$null
        $usable = $LASTEXITCODE -eq 0
    } catch { $usable = $false }
}
if (-not $usable) {
    $python = Find-Python
    if (-not $python) {
        Write-Host 'Installing Python 3.13 for the current user...'
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if ($winget) {
            & $winget.Source install --id Python.Python.3.13 --exact --source winget --scope user --silent --accept-source-agreements --accept-package-agreements
            $python = Find-Python
        }
        if (-not $python) {
            $version = '3.13.9'
            $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { '-arm64' } elseif ([Environment]::Is64BitOperatingSystem) { '-amd64' } else { '' }
            $installer = Join-Path $env:TEMP ("qr-python-" + [guid]::NewGuid() + ".exe")
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -UseBasicParsing "https://www.python.org/ftp/python/$version/python-$version$arch.exe" -OutFile $installer
                $signature = Get-AuthenticodeSignature -FilePath $installer
                if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Python Software Foundation(,|$)') {
                    throw 'Invalid Python Software Foundation installer signature.'
                }
                $process = Start-Process -FilePath $installer -ArgumentList '/quiet InstallAllUsers=0 Include_launcher=0 Include_test=0 Include_pip=1' -Wait -PassThru
                if ($process.ExitCode -ne 0) { throw "Python installation failed ($($process.ExitCode))." }
            } finally { Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue }
            $python = Find-Python
        }
    }
    if (-not $python) { throw 'Could not locate Python 3.11+ after installation.' }
    & $python -m venv --clear (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare .venv.' }
}

& $VenvPython -m pip --disable-pip-version-check install -r requirements-runtime.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check internet access and restart run_qr.bat.' }

& $VenvPython install_step_runtime.py
if ($PrepareOnly) { exit 0 }
$env:PYTHONPATH = Join-Path $PSScriptRoot "server"
& $VenvPython -m qr_server.launcher --open-browser
exit $LASTEXITCODE
