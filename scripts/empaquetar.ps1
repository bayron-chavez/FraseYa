param([string]$Python = 'venv/Scripts/python.exe')
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    & $Python -m PyInstaller --noconfirm --clean FraseYa.spec
    if ($LASTEXITCODE -ne 0) { throw 'Falló PyInstaller.' }
    Copy-Item -LiteralPath 'docs/MANUAL_USUARIO.md' -Destination 'dist/FraseYa/MANUAL_USUARIO.md'
    Copy-Item -LiteralPath 'docs/GUIA_ADMINISTRADOR.md' -Destination 'dist/FraseYa/GUIA_ADMINISTRADOR.md'
    Copy-Item -LiteralPath 'docs/INTERFAZ_QT.md', 'docs/LICENCIAS_QT.md', 'docs/AUDITORIA_QT_2026-10-10.md' -Destination 'dist/FraseYa'
    Compress-Archive -Path 'dist/FraseYa' -DestinationPath 'dist/FraseYa-portable.zip' -Force
} finally { Pop-Location }
