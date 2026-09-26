# refresh_weekly.ps1
# Actualizacion semanal automatica del pipeline Football Predictor.
# Pensado para correr como Windows Task Scheduler job, todos los martes 6:00 AM
# hora de El Salvador (hora local de esta PC).
#
# Orden: extraccion (bronze) -> silver -> gold (ratings, predictions, simulations)
# -> commit + push a GitHub SOLO si hubo cambios en data/. Streamlit Cloud
# redeploya solo al detectar el push. Si algun notebook falla, se aborta y
# NO se hace push (nunca se sube data a medio actualizar).

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\arnol\OneDrive\Documentos\Progaming\Datascience\datascience\football_predictor"
$CondaEnv    = "coinvision_env312"
$LogFile     = Join-Path $ProjectRoot "logs\weekly_refresh.log"

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "logs") | Out-Null

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $LogFile -Append
}

Set-Location $ProjectRoot
Log "===== Iniciando refresh semanal ====="

$notebooks = @(
    "Football_Data_Extraction.ipynb",
    "Matches_Silver_Builder.ipynb",
    "Team_Ratings_Builder.ipynb",
    "Match_Predictions_Builder.ipynb",
    "Season_Simulations_Builder.ipynb"
)

$failed = $false
foreach ($nb in $notebooks) {
    Log "Ejecutando $nb ..."
    & conda run -n $CondaEnv jupyter nbconvert --to notebook --execute --inplace "$nb" *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: $nb fallo (exit $LASTEXITCODE). Abortando, no se hace push."
        $failed = $true
        break
    }
    Log "$nb OK"
}

if ($failed) {
    Log "===== Refresh terminado CON ERRORES ====="
    exit 1
}

$changes = git status --porcelain -- data
if ([string]::IsNullOrWhiteSpace($changes)) {
    Log "Sin cambios en data/ -- nada que subir."
    Log "===== Refresh terminado (sin cambios) ====="
    exit 0
}

git add data
git commit -m "Actualizacion automatica semanal: resultados y proyecciones al $(Get-Date -Format 'yyyy-MM-dd')"
git push origin main *>> $LogFile

if ($LASTEXITCODE -ne 0) {
    Log "ERROR: git push fallo (exit $LASTEXITCODE). Revisa credenciales SSH."
    exit 1
}

Log "Push OK -- Streamlit Cloud va a redeployar solo con los datos nuevos."
Log "===== Refresh terminado OK ====="
