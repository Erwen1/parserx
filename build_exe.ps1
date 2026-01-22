[CmdletBinding()]
param(
    [string]$Proxy = $env:HTTPS_PROXY,
    [switch]$BuildCli
)

$ErrorActionPreference = 'Stop'

# PowerShell 7 can treat native stderr output as errors when ErrorActionPreference=Stop.
# PyInstaller logs may go to stderr even on success. Disable that behavior when available.
try {
    if ($PSVersionTable.PSVersion.Major -ge 7) {
        $global:PSNativeCommandUseErrorActionPreference = $false
    }
} catch {
    # Ignore if variable/version is not supported
}

Write-Host "== XTI Viewer - Build Onefile EXE ==" -ForegroundColor Cyan

# PySide6 is huge. If you use --collect-all PySide6, PyInstaller will include
# many optional Qt modules (QML/Quick/WebEngine/PDF/3D/...) even if unused.
# We keep only what the app uses (QtCore/QtGui/QtWidgets) by *not* collecting
# everything, and explicitly excluding big modules.
$qtExcludes = @(
    # QML / Quick
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuick3D',
    'PySide6.QtQuickControls2',
    'PySide6.QtQuickTest',
    'PySide6.QtQuickWidgets',
    'PySide6.QtQmlCompiler',
    # WebEngine
    'PySide6.QtWebChannel',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets',
    # PDF
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    # 3D
    'PySide6.Qt3DAnimation',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic',
    'PySide6.Qt3DRender',
    # Multimedia / audio
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtSpatialAudio',
    'PySide6.QtTextToSpeech',
    # Location / sensors / device
    'PySide6.QtLocation',
    'PySide6.QtPositioning',
    'PySide6.QtBluetooth',
    'PySide6.QtNfc',
    'PySide6.QtSensors',
    # Serial / remote / SCXML
    'PySide6.QtSerialBus',
    'PySide6.QtSerialPort',
    'PySide6.QtRemoteObjects',
    'PySide6.QtScxml',
    # Data / DB / graphs
    'PySide6.QtCharts',
    'PySide6.QtDataVisualization',
    'PySide6.QtGraphs',
    'PySide6.QtGraphsWidgets',
    'PySide6.QtSql',
    # Misc
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'PySide6.QtTest',
    'PySide6.QtUiTools',
    'PySide6.QtXml',
    'PySide6.QtXmlPatterns'
)

# Use system Python 3.13 if present, else fallback to py launcher
$python = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python313/python.exe'
if (-not (Test-Path $python)) {
    $python = 'py'
}

if ($Proxy) {
    Write-Host "Setting proxy: $Proxy" -ForegroundColor Yellow
    $env:HTTP_PROXY = $Proxy
    $env:HTTPS_PROXY = $Proxy
    [Environment]::SetEnvironmentVariable('HTTP_PROXY', $Proxy, 'User')
    [Environment]::SetEnvironmentVariable('HTTPS_PROXY', $Proxy, 'User')
}

# Ensure PyInstaller is available (pin version known to work here)
Write-Host "Installing/ensuring PyInstaller..." -ForegroundColor Cyan
if ($python -eq 'py') {
    py -3 -m pip install --disable-pip-version-check --timeout 120 `
        $(if ($Proxy) {"--proxy=$Proxy"}) pyinstaller==6.11.1 | Out-Host
} else {
    & $python -m pip install --disable-pip-version-check --timeout 120 `
        $(if ($Proxy) {"--proxy=$Proxy"}) pyinstaller==6.11.1 | Out-Host
}

# Ensure we can generate a Windows .ico from the provided Logo.png
Write-Host "Ensuring Pillow (for icon conversion)..." -ForegroundColor Cyan
if ($python -eq 'py') {
    py -3 -m pip install --disable-pip-version-check --timeout 120 `
        $(if ($Proxy) {"--proxy=$Proxy"}) pillow | Out-Host
} else {
    & $python -m pip install --disable-pip-version-check --timeout 120 `
        $(if ($Proxy) {"--proxy=$Proxy"}) pillow | Out-Host
}

# Convert Logo.png -> Logo.ico (best effort)
if (Test-Path .\Logo.png) {
    Write-Host "Generating Logo.ico from Logo.png..." -ForegroundColor Cyan
    $convertCode = @'
from PIL import Image

img = Image.open('Logo.png')
sizes = [(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]
img.save('Logo.ico', format='ICO', sizes=sizes)
print('Wrote Logo.ico')
'@
    if ($python -eq 'py') {
        py -3 -c $convertCode | Out-Host
    } else {
        & $python -c $convertCode | Out-Host
    }
} else {
    Write-Host "WARNING: Logo.png not found at repo root. Icon will not be updated." -ForegroundColor Yellow
}

# Stop running app processes that may lock dist\*.exe
Write-Host "Stopping any running XTIViewer processes..." -ForegroundColor Cyan
try {
    Get-Process -Name XTIViewer, XTIViewerCLI -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 600
} catch {
    # ignore
}

# Clean previous artifacts and specs so CLI flags are honored
Write-Host "Cleaning dist/, build/, and old spec..." -ForegroundColor Cyan
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Filter "*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# If Windows still holds a lock (Explorer/AV), dist\*.exe may survive the delete.
foreach ($p in @('.\dist\XTIViewer.exe', '.\dist\XTIViewerCLI.exe')) {
    if (Test-Path $p) {
        Write-Host "Removing locked artifact: $p" -ForegroundColor Yellow
        try {
            attrib -R -S -H $p 2>$null
        } catch {
            # ignore
        }
        try {
            Remove-Item -Force $p -ErrorAction Stop
        } catch {
            throw "Cannot delete $p (likely still running or locked). Close the app (and any Explorer preview) and retry."
        }
    }
}

# Build (GUI app, packs PySide6 assets). Adjust name/icon as needed
$guiArgs = @(
    '--noconfirm',
    '--clean',
    '--onefile',
    '--windowed',
    '--name', 'XTIViewer',
    'xti_viewer/main.py'
)

if (Test-Path .\Logo.ico) {
    $guiArgs += @('--icon', (Resolve-Path .\Logo.ico))
}
if (Test-Path .\Logo.png) {
    # Include logo for runtime (used by QIcon/QPixmap in the app)
    $guiArgs += @('--add-data', "Logo.png;.")
}

# Exclude unused/huge Qt modules (helps a lot for onefile size).
foreach ($m in $qtExcludes) {
    $guiArgs += @('--exclude-module', $m)
}
Write-Host ("pyinstaller " + ($guiArgs -join ' ')) -ForegroundColor Green
$oldEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    if ($python -eq 'py') {
        py -3 -m PyInstaller @guiArgs 2>&1 | Out-Host
    } else {
        & $python -m PyInstaller @guiArgs 2>&1 | Out-Host
    }
} finally {
    $ErrorActionPreference = $oldEap
}
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller GUI build failed with exit code $LASTEXITCODE"
}

if ($BuildCli) {
    $cliArgs = @(
        '--noconfirm',
        '--clean',
        '--onefile',
        '--console',
        '--name', 'XTIViewerCLI',
        'xti_viewer/cli.py'
    )

    if (Test-Path .\Logo.ico) {
        $cliArgs += @('--icon', (Resolve-Path .\Logo.ico))
    }
    Write-Host ("pyinstaller " + ($cliArgs -join ' ')) -ForegroundColor Green
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($python -eq 'py') {
            py -3 -m PyInstaller @cliArgs 2>&1 | Out-Host
        } else {
            & $python -m PyInstaller @cliArgs 2>&1 | Out-Host
        }
    } finally {
        $ErrorActionPreference = $oldEap
    }
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller CLI build failed with exit code $LASTEXITCODE"
    }
}

# Show output
if (Test-Path .\dist\XTIViewer.exe) {
    Write-Host "Success: dist\\XTIViewer.exe" -ForegroundColor Green
} elseif (Test-Path .\dist\XTIViewer\XTIViewer.exe) {
    Write-Host "Success (onedir layout): dist\\XTIViewer\\XTIViewer.exe" -ForegroundColor Yellow
} else {
    Write-Host "Build finished but no exe found in dist/. Check logs above." -ForegroundColor Red
    exit 1
}

if ($BuildCli) {
    if (Test-Path .\dist\XTIViewerCLI.exe) {
        Write-Host "Success: dist\\XTIViewerCLI.exe" -ForegroundColor Green
    } elseif (Test-Path .\dist\XTIViewerCLI\XTIViewerCLI.exe) {
        Write-Host "Success (onedir layout): dist\\XTIViewerCLI\\XTIViewerCLI.exe" -ForegroundColor Yellow
    } else {
        Write-Host "CLI build finished but no CLI exe found in dist/. Check logs above." -ForegroundColor Red
        exit 1
    }
}
