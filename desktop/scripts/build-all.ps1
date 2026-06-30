# Full desktop build - API + Web + Electron packaging
# Output: desktop/dist/Strontium Agent Setup x.y.z.exe (NSIS installer)

$ErrorActionPreference = "Stop"

$scriptDir  = $PSScriptRoot
$repoRoot   = Resolve-Path "$scriptDir\..\.."
$desktopDir = Join-Path $repoRoot "desktop"

Write-Host "==== Phase 1: FastAPI bundling ====" -ForegroundColor Magenta
& (Join-Path $scriptDir "build-api.ps1")
if ($LASTEXITCODE -ne 0) { throw "API build failed" }

Write-Host ""
Write-Host "==== Phase 2: Next.js build ====" -ForegroundColor Magenta
& (Join-Path $scriptDir "build-web.ps1")
if ($LASTEXITCODE -ne 0) { throw "Web build failed" }

Write-Host ""
Write-Host "==== Phase 3: Electron packaging ====" -ForegroundColor Magenta
Push-Location $desktopDir
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing desktop dependencies..." -ForegroundColor Yellow
        yarn install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { throw "desktop yarn install failed" }
    }

    yarn dist
    if ($LASTEXITCODE -ne 0) { throw "electron-builder failed" }

    Write-Host ""
    Write-Host "==== Done ====" -ForegroundColor Green
    $installer = Get-ChildItem "dist" -Filter "*Setup*.exe" | Select-Object -First 1
    if ($installer) {
        $sizeMB = [math]::Round($installer.Length / 1MB, 1)
        Write-Host "Installer: $($installer.FullName) (${sizeMB}MB)" -ForegroundColor Green
    } else {
        Write-Host "Warning: installer not found. Check desktop/dist/" -ForegroundColor Yellow
    }
}
finally {
    Pop-Location
}
