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

Set-Location $ProjectRoot
Log "===== Starting weekly refresh ====="

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
    & conda run -n $CondaEnv jupyter nbconvert --to notebook --execute --inplace "$nb" *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: $nb failed (exit $LASTEXITCODE). Aborting, no push."
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
git push origin main *>> $LogFile

if ($LASTEXITCODE -ne 0) {
    Log "ERROR: git push failed (exit $LASTEXITCODE). Check your git credentials."
    exit 1
}

Log "Push OK -- Streamlit Cloud will redeploy on its own with the new data."
Log "===== Refresh finished OK ====="
