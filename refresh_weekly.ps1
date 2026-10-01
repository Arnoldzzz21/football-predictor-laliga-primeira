# refresh_weekly.ps1
# Automatic weekly refresh of the Football Predictor pipeline.
# Meant to run as a Windows Task Scheduler job, every Tuesday at 6:00 AM
# El Salvador time (local time of this PC).
#
# Order: extraction (bronze) -> silver -> gold (ratings, predictions, simulations)
# -> commit + push to GitHub ONLY if data/ changed. Streamlit Cloud
# redeploys on its own when it detects the push. If any notebook fails, it
# aborts and does NOT push (half-updated data is never uploaded).

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$LogFile     = Join-Path $ProjectRoot "logs\weekly_refresh.log"

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "logs") | Out-Null

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $LogFile -Append
}

# Task Scheduler does not load the user's shell setup, so nothing can be
# assumed to be on PATH. The notebooks run with a Python interpreter located
# explicitly, in this order:
#   1. $env:FOOTBALL_PYTHON, if set (full path to python.exe), else
#   2. the first per-user Python install (newest first) under
#      %LOCALAPPDATA%\Programs\Python that can import every package the
#      pipeline needs, including nbconvert and ipykernel.
function Test-PythonEnv($exe) {
    $ErrorActionPreference = "Continue"   # native stderr must not abort the script
    & $exe -c "import pandas, pyarrow, scipy, yaml, numpy, nbconvert, ipykernel" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Find-Python {
    if ($env:FOOTBALL_PYTHON -and (Test-Path $env:FOOTBALL_PYTHON)) { return $env:FOOTBALL_PYTHON }

    $root = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (-not (Test-Path $root)) { return $null }
    $candidates = Get-ChildItem $root -Directory -Filter "Python3*" |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "python.exe" } |
        Where-Object { Test-Path $_ }
    foreach ($exe in $candidates) {
        if (Test-PythonEnv $exe) { return $exe }
    }
    return $null
}

Set-Location $ProjectRoot
Log "===== Starting weekly refresh ====="

$PythonExe = Find-Python
if (-not $PythonExe) {
    Log "ERROR: no Python with pandas, pyarrow, scipy, pyyaml, numpy, nbconvert and ipykernel was found."
    Log "Install the missing packages, or set the FOOTBALL_PYTHON user environment variable to the full path of the right python.exe."
    Log "===== Refresh finished WITH ERRORS ====="
    exit 1
}
Log "Using python: $PythonExe"

$notebooks = @(
    "Football_Data_Extraction.ipynb",
    "Matches_Silver_Builder.ipynb",
    "Team_Ratings_Builder.ipynb",
    "Match_Predictions_Builder.ipynb",
    "Season_Simulations_Builder.ipynb"
)

$failed = $false
foreach ($nb in $notebooks) {
    Log "Running $nb ..."
    # Windows PowerShell 5.1 turns anything a native command writes to stderr
    # into a terminating error when $ErrorActionPreference is "Stop" and its
    # output is redirected (nbconvert logs progress to stderr). So relax
    # it only around the native call and rely on the exit code instead.
    $ErrorActionPreference = "Continue"
    & $PythonExe -m nbconvert --to notebook --execute --inplace "$nb" *>> $LogFile
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($exitCode -ne 0) {
        Log "ERROR: $nb failed (exit $exitCode). Aborting, no push."
        $failed = $true
        break
    }
    Log "$nb OK"
}

if ($failed) {
    Log "===== Refresh finished WITH ERRORS ====="
    exit 1
}

$changes = git status --porcelain -- data
if ([string]::IsNullOrWhiteSpace($changes)) {
    Log "No changes in data/ -- nothing to upload."
    Log "===== Refresh finished (no changes) ====="
    exit 0
}

git add data
git commit -m "Automatic weekly update: results and projections as of $(Get-Date -Format 'yyyy-MM-dd')"

# Same stderr caveat as above: git writes push progress to stderr.
$ErrorActionPreference = "Continue"
git push origin main *>> $LogFile
$pushCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"

if ($pushCode -ne 0) {
    Log "ERROR: git push failed (exit $pushCode). Check your git credentials."
    exit 1
}

Log "Push OK -- Streamlit Cloud will redeploy on its own with the new data."
Log "===== Refresh finished OK ====="
