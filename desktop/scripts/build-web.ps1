# Build Next.js frontend in standalone mode -> ../web-out/
# Output:
#   web-out/server.js        (Next.js standalone server)
#   web-out/.next/           (server code + build output)
#   web-out/.next/static/    (static assets - standalone mode excludes these by default)
#   web-out/public/          (includes env-config.js)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$webDir   = Join-Path $repoRoot "web"
$outDir   = Join-Path $repoRoot "web-out"

Write-Host "==> [1/3] Next.js build (standalone)" -ForegroundColor Cyan
Push-Location $webDir
try {
    yarn install --frozen-lockfile --silent
    if ($LASTEXITCODE -ne 0) { throw "yarn install failed" }

    # Pre-generate runtime env-config.js so it gets bundled into standalone.
    # Electron main overrides NEXT_PUBLIC_API_URL at runtime if needed.
    $envConfig = Join-Path $webDir "public\env-config.js"
    @"
window.__ENV__ = {
  NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000",
};
"@ | Set-Content -Encoding UTF8 -NoNewline $envConfig

    yarn build
    if ($LASTEXITCODE -ne 0) { throw "yarn build failed" }
}
finally {
    Pop-Location
}

Write-Host "==> [2/3] Copy standalone output -> $outDir" -ForegroundColor Cyan
if (Test-Path $outDir) {
    Remove-Item -Recurse -Force $outDir
}
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

$standalone = Join-Path $webDir ".next\standalone"
if (-not (Test-Path $standalone)) { throw "standalone output missing: $standalone" }

# Copy whole standalone tree (includes node_modules)
Copy-Item -Recurse (Join-Path $standalone "*") $outDir

# standalone mode requires manually copying .next/static and public
$staticSrc = Join-Path $webDir ".next\static"
$staticDst = Join-Path $outDir ".next\static"
if (Test-Path $staticSrc) {
    New-Item -ItemType Directory -Path (Split-Path $staticDst) -Force | Out-Null
    Copy-Item -Recurse $staticSrc $staticDst
}

$publicSrc = Join-Path $webDir "public"
if (Test-Path $publicSrc) {
    Copy-Item -Recurse $publicSrc $outDir
}

Write-Host "==> [3/3] Verify" -ForegroundColor Cyan
$serverJs = Join-Path $outDir "server.js"
if (-not (Test-Path $serverJs)) { throw "server.js missing" }
$dirSizeMB = [math]::Round(((Get-ChildItem -Recurse $outDir | Measure-Object -Property Length -Sum).Sum / 1MB), 1)
Write-Host "OK - web-out: ${dirSizeMB}MB" -ForegroundColor Green
Write-Host "    location: $outDir" -ForegroundColor DarkGray
