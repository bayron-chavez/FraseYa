$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    python -m PyInstaller --noconfirm --clean FraseYa.spec
    if ($LASTEXITCODE -ne 0) { throw 'Falló PyInstaller.' }
    Copy-Item -LiteralPath 'docs/MANUAL_USUARIO.md' -Destination 'dist/FraseYa/MANUAL_USUARIO.md'
    Copy-Item -LiteralPath 'docs/GUIA_ADMINISTRADOR.md' -Destination 'dist/FraseYa/GUIA_ADMINISTRADOR.md'
    Compress-Archive -Path 'dist/FraseYa' -DestinationPath 'dist/FraseYa-portable.zip' -Force
} finally { Pop-Location }
