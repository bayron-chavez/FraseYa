param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno virtual.' }
    }
    & './.venv/Scripts/python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias. Revisa la conexión a internet.' }
    & './.venv/Scripts/python.exe' -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Las pruebas requieren revisión.' }
    Write-Host 'Entorno preparado y pruebas aprobadas.'
} finally {
    Pop-Location
}
