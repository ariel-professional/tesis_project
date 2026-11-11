param(
    [string]$ArchivePath = "",
    [string]$UvExecutable = "uv"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$expectedSha256 = "4ACBED6DD1C744B0376E3B1CF57CE906F9DC9E95E68824584C8099A63025A3C3"
$desktopRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repositoryRoot = (Resolve-Path (Join-Path $desktopRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($ArchivePath)) {
    $ArchivePath = Join-Path $desktopRoot "python-3.12.10-embed-amd64.zip"
}
$resolvedArchive = (Resolve-Path -LiteralPath $ArchivePath).Path
$actualSha256 = (Get-FileHash -LiteralPath $resolvedArchive -Algorithm SHA256).Hash
if ($actualSha256 -ne $expectedSha256) {
    throw "CPython archive SHA-256 mismatch: $actualSha256"
}

$resourcesRoot = Join-Path $desktopRoot "resources"
$target = Join-Path $resourcesRoot "python"
$staging = Join-Path $resourcesRoot "python.staging"
$resolvedResources = [System.IO.Path]::GetFullPath($resourcesRoot)
$resolvedTarget = [System.IO.Path]::GetFullPath($target)
$resolvedStaging = [System.IO.Path]::GetFullPath($staging)
if (-not $resolvedTarget.StartsWith($resolvedResources) -or -not $resolvedStaging.StartsWith($resolvedResources)) {
    throw "Refusing to assemble Python outside desktop/resources."
}

if (Test-Path -LiteralPath $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging | Out-Null
Expand-Archive -LiteralPath $resolvedArchive -DestinationPath $staging

$pthFile = Get-ChildItem -LiteralPath $staging -Filter "python312._pth" -File -ErrorAction Stop
@("python312.zip", ".", "Lib/site-packages", "import site") |
    Set-Content -LiteralPath $pthFile.FullName -Encoding ascii
$sitePackages = Join-Path $staging "Lib\site-packages"
New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null

$buildRoot = Join-Path $staging ".build"
New-Item -ItemType Directory -Path $buildRoot | Out-Null
$requirements = Join-Path $buildRoot "requirements.txt"
& $UvExecutable export --project $repositoryRoot --locked --no-dev --no-emit-project `
    --format requirements-txt --output-file $requirements
if ($LASTEXITCODE -ne 0) { throw "uv export failed." }
& $UvExecutable pip install --target $sitePackages --python-version 3.12 `
    --python-platform x86_64-pc-windows-msvc --require-hashes --requirements $requirements
if ($LASTEXITCODE -ne 0) { throw "Installing locked runtime dependencies failed." }

& $UvExecutable build --project $repositoryRoot --wheel --out-dir $buildRoot
if ($LASTEXITCODE -ne 0) { throw "Building the application wheel failed." }
$applicationWheel = Get-ChildItem -LiteralPath $buildRoot -Filter "tesis_proyect-*.whl" -File |
    Select-Object -First 1
if ($null -eq $applicationWheel) { throw "The application wheel was not produced." }
& $UvExecutable pip install --target $sitePackages --no-deps $applicationWheel.FullName
if ($LASTEXITCODE -ne 0) { throw "Installing the application wheel failed." }

Remove-Item -LiteralPath $buildRoot -Recurse -Force
& (Join-Path $staging "python.exe") -I -m tesis_desktop_gateway.cli --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw "The embedded gateway smoke test failed." }

if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
}
New-Item -ItemType Directory -Path $target | Out-Null
Copy-Item -Path (Join-Path $staging "*") -Destination $target -Recurse -Force
& (Join-Path $target "python.exe") -I -m tesis_desktop_gateway.cli --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw "The published embedded gateway smoke test failed." }
Remove-Item -LiteralPath $staging -Recurse -Force
Write-Output "Embedded CPython 3.12.10 assembled at $target"
