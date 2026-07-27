$ErrorActionPreference = "Stop"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

function Get-WindowsGrypeExecutable(
    [string]$DataDirectory,
    [string]$GrypeWorkPath
) {
    $Version = "0.112.0"
    $ExpectedArchiveSha256 = (
        "94ae49ced125fca7590fd35dfa96e36f68760cefff9a653c92fa8f6842777879"
    )
    $ExpectedExecutableSha256 = (
        "752108b8dbf71be11dc5620e6d419caff1b4e71a0f92d9a7d35acabe725c907a"
    )
    $ToolDirectory = Join-Path $DataDirectory "security-tools/grype-$Version-windows-amd64"
    $ExecutablePath = Join-Path $ToolDirectory "grype.exe"

    if (Test-Path -LiteralPath $ExecutablePath) {
        $ActualExecutableSha256 = (
            Get-FileHash -LiteralPath $ExecutablePath -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($ActualExecutableSha256 -eq $ExpectedExecutableSha256) {
            return $ExecutablePath
        }
    }

    $ArchivePath = Join-Path $GrypeWorkPath "grype_$($Version)_windows_amd64.zip"
    $DownloadUrl = (
        "https://github.com/anchore/grype/releases/download/v$Version/" +
        "grype_$($Version)_windows_amd64.zip"
    )
    Invoke-WebRequest -UseBasicParsing -Uri $DownloadUrl -OutFile $ArchivePath
    $ActualArchiveSha256 = (
        Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if ($ActualArchiveSha256 -ne $ExpectedArchiveSha256) {
        throw "Downloaded Grype archive failed the pinned SHA-256 check."
    }

    $ExtractPath = Join-Path $GrypeWorkPath "grype-extracted"
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ExtractPath -Force
    $StagedExecutablePath = Join-Path $ExtractPath "grype.exe"
    $ActualExecutableSha256 = (
        Get-FileHash -LiteralPath $StagedExecutablePath -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if ($ActualExecutableSha256 -ne $ExpectedExecutableSha256) {
        throw "Extracted Grype executable failed the pinned SHA-256 check."
    }

    New-Item -ItemType Directory -Path $ToolDirectory -Force | Out-Null
    Copy-Item -LiteralPath $StagedExecutablePath -Destination $ExecutablePath -Force
    return $ExecutablePath
}

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$DataDirectory = Join-Path $RepositoryRoot ".data"
$GrypeWorkPath = Join-Path $DataDirectory (
    "grype-scan-" + [System.Guid]::NewGuid().ToString("N")
)
$GrypeCachePath = Join-Path $GrypeWorkPath "cache"
$GrypeTempPath = Join-Path $GrypeWorkPath "temp"
New-Item -ItemType Directory -Path $GrypeCachePath, $GrypeTempPath -Force | Out-Null
Push-Location $RepositoryRoot

try {
    docker run --rm --network none --volume "${RepositoryRoot}:/repo:ro" `
        ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f `
        dir /repo --config /repo/.gitleaks.toml --redact --exit-code 1 `
        --verbose --no-color
    Assert-LastExitCode "Gitleaks"

    pnpm audit --audit-level high
    Assert-LastExitCode "pnpm audit"

    uv sync --frozen --all-packages --all-groups
    Assert-LastExitCode "Python workspace dependency sync"
    uv run --package careeros-api --with pip-audit==2.10.1 pip-audit
    Assert-LastExitCode "Python workspace pip-audit"

    foreach ($Service in @("api", "worker", "web", "web-edge")) {
        docker compose build $Service
        Assert-LastExitCode "Application image build for $Service"
    }

    foreach ($RuntimeImage in @("careeros-api:latest", "careeros-worker:latest")) {
        docker run --rm $RuntimeImage python -c (
            "import os, ssl; " +
            "assert os.getuid() == 10001; " +
            "assert ssl.OPENSSL_VERSION.startswith('OpenSSL 3.5.7 ')"
        )
        Assert-LastExitCode "Non-root/OpenSSL runtime smoke for $RuntimeImage"
    }

    $Images = @(
        "careeros-api:latest",
        "careeros-worker:latest",
        "careeros-web:latest",
        "careeros-web-edge:latest"
    )
    $NativeGrypeExecutable = $null
    if ($env:OS -eq "Windows_NT") {
        $NativeGrypeExecutable = Get-WindowsGrypeExecutable `
            -DataDirectory $DataDirectory `
            -GrypeWorkPath $GrypeWorkPath
    }

    foreach ($Image in $Images) {
        $ArchiveName = ($Image -replace "[^a-zA-Z0-9_.-]", "-") + ".tar"
        $ArchivePath = Join-Path $GrypeWorkPath $ArchiveName
        docker image save --output $ArchivePath $Image
        Assert-LastExitCode "Image archive export for $Image"

        if ($null -ne $NativeGrypeExecutable) {
            $PreviousGrypeDbCacheDirectory = $env:GRYPE_DB_CACHE_DIR
            $PreviousTempDirectory = $env:TEMP
            $PreviousTmpDirectory = $env:TMP
            $env:GRYPE_DB_CACHE_DIR = $GrypeCachePath
            $env:TEMP = $GrypeTempPath
            $env:TMP = $GrypeTempPath
            try {
                & $NativeGrypeExecutable `
                    "docker-archive:$ArchivePath" `
                    --config "$RepositoryRoot/.grype.yaml" `
                    --fail-on high `
                    --only-fixed
            }
            finally {
                if ($null -eq $PreviousGrypeDbCacheDirectory) {
                    Remove-Item Env:GRYPE_DB_CACHE_DIR -ErrorAction SilentlyContinue
                }
                else {
                    $env:GRYPE_DB_CACHE_DIR = $PreviousGrypeDbCacheDirectory
                }
                $env:TEMP = $PreviousTempDirectory
                $env:TMP = $PreviousTmpDirectory
            }
        }
        else {
            docker run --rm `
                --volume "${GrypeWorkPath}:/work:ro" `
                --volume "${RepositoryRoot}/.grype.yaml:/etc/grype.yaml:ro" `
                --volume "${GrypeCachePath}:/root/.cache/grype" `
                anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d `
                "docker-archive:/work/$ArchiveName" `
                --config /etc/grype.yaml --fail-on high --only-fixed
        }
        Assert-LastExitCode "Grype scan for $Image"

        Remove-Item -LiteralPath $ArchivePath -Force
    }

    Write-Host "CareerOS security scans passed."
}
finally {
    Pop-Location
    if (Test-Path -LiteralPath $GrypeWorkPath) {
        $ResolvedDataDirectory = [System.IO.Path]::GetFullPath($DataDirectory).TrimEnd(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        )
        $ResolvedGrypeWorkPath = [System.IO.Path]::GetFullPath($GrypeWorkPath)
        $ExpectedPrefix = $ResolvedDataDirectory + [System.IO.Path]::DirectorySeparatorChar
        if (
            -not $ResolvedGrypeWorkPath.StartsWith(
                $ExpectedPrefix,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            throw "Refusing to remove Grype work directory outside .data: $ResolvedGrypeWorkPath"
        }
        Remove-Item -LiteralPath $ResolvedGrypeWorkPath -Recurse -Force
    }
}
