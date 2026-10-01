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
$CondaEnv    = "coinvision_env312"
$LogFile     = Join-Path $ProjectRoot "logs\weekly_refresh.log"

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "logs") | Out-Null

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $LogFile -Append
}

# Task Scheduler does not load the user's shell setup, so `conda` is usually
# NOT on PATH when this script runs from a scheduled task. Instead of relying
# on PATH, look for conda.exe in the usual install locations.
function Find-Conda {
    if ($env:CONDA_EXE -and (Test-Path $env:CONDA_EXE)) { return $env:CONDA_EXE }

    $onPath = Get-Command conda -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    $roots = @(
        "$env:USERPROFILE\anaconda3",
        "$env:USERPROFILE\miniconda3",
        "$env:LOCALAPPDATA\anaconda3",
        "$env:LOCALAPPDATA\miniconda3",
        "C:\ProgramData\anaconda3",
        "C:\ProgramData\miniconda3"
    )
    foreach ($root in $roots) {
        $exe = Join-Path $root "Scripts\conda.exe"
        if (Test-Path $exe) { return $exe }
    }
    return $null
}

Set-Location $ProjectRoot
Log "===== Starting weekly refresh ====="

$CondaExe = Find-Conda
if (-not $CondaExe) {
    Log "ERROR: conda.exe not found (not on PATH and not in the usual install folders)."
    Log "Run 'conda info --base' in an Anaconda Prompt and add that folder to the roots list in Find-Conda."
    Log "===== Refresh finished WITH ERRORS ====="
    exit 1
}
Log "Using conda: $CondaExe"

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
    # output is redirected (conda/jupyter log progress to stderr). So relax
    # it only around the native call and rely on the exit code instead.
    $ErrorActionPreference = "Continue"
    & $CondaExe run -n $CondaEnv jupyter nbconvert --to notebook --execute --inplace "$nb" *>> $LogFile
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
