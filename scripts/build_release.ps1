$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Missing virtual-environment Python: $python"
}

function Resolve-ProjectChild([string] $name) {
    $candidate = [IO.Path]::GetFullPath((Join-Path $projectRoot $name))
    $rootWithSeparator = $projectRoot.TrimEnd('\') + '\'
    if (-not $candidate.StartsWith($rootWithSeparator, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside project root: $candidate"
    }
    return $candidate
}

$buildDir = Resolve-ProjectChild "build"
$distDir = Resolve-ProjectChild "dist"
foreach ($directory in @($buildDir, $distDir)) {
    if (Test-Path -LiteralPath $directory) {
        Remove-Item -LiteralPath $directory -Recurse -Force
    }
}

$env:QT_QPA_PLATFORM = "offscreen"
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed with exit code $LASTEXITCODE" }

& $python -m PyInstaller --noconfirm (Join-Path $projectRoot "CHI-OPEIS.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$bundleDir = Join-Path $distDir "CHI-OPEIS"
$exe = Join-Path $bundleDir "CHI-OPEIS.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Expected executable was not created: $exe"
}
$smokeProcess = Start-Process -FilePath $exe -ArgumentList "--smoke-test" -WindowStyle Hidden -Wait -PassThru
if ($smokeProcess.ExitCode -ne 0) { throw "Packaged smoke test failed with exit code $($smokeProcess.ExitCode)" }

$version = (& $python -c "import importlib.metadata as m; print(m.version('opeis-master'))").Trim()
$archive = Join-Path $distDir ("CHI-OPEIS-{0}-windows-x64.zip" -f $version)
Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $archive -Force
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    throw "Expected archive was not created: $archive"
}

$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
"{0}  {1}" -f $hash, (Split-Path $archive -Leaf) | Set-Content -LiteralPath (Join-Path $distDir "SHA256SUMS.txt") -Encoding ASCII
Write-Host "Bundle:  $bundleDir"
Write-Host "Archive: $archive"
Write-Host "SHA256:  $hash"
