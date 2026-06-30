# Build FastAPI backend with PyInstaller -> ../api-dist/strontium_agent/
# Output: api-dist/strontium_agent/strontium_agent.exe + dynamic libs (onedir)
# Entry point: api/run_local.py

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$apiDir   = Join-Path $repoRoot "api"
$distDir  = Join-Path $repoRoot "api-dist"

Write-Host "==> [1/3] Check PyInstaller" -ForegroundColor Cyan
Push-Location $apiDir
try {
    uv run python -c "import PyInstaller; print('PyInstaller', PyInstaller.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "PyInstaller not installed. Installing..." -ForegroundColor Yellow
        uv add --dev pyinstaller
        if ($LASTEXITCODE -ne 0) { throw "pyinstaller install failed" }
    }

    Write-Host "==> [2/3] Running PyInstaller (onedir)" -ForegroundColor Cyan
    if (Test-Path $distDir) {
        Write-Host "Removing existing api-dist: $distDir" -ForegroundColor DarkGray
        Remove-Item -Recurse -Force $distDir
    }

    uv run pyinstaller strontium_agent.spec --noconfirm --distpath $distDir
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

    Write-Host "==> [3/3] Verify output" -ForegroundColor Cyan
    $exe = Join-Path $distDir "strontium_agent\strontium_agent.exe"
    if (-not (Test-Path $exe)) { throw "expected output missing: $exe" }
    $sizeMB = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    $dirSizeMB = [math]::Round(((Get-ChildItem -Recurse (Join-Path $distDir "strontium_agent") | Measure-Object -Property Length -Sum).Sum / 1MB), 1)
    Write-Host "OK - strontium_agent.exe: ${sizeMB}MB, total dir: ${dirSizeMB}MB" -ForegroundColor Green
    Write-Host "    location: $distDir" -ForegroundColor DarkGray
}
finally {
    Pop-Location
}
