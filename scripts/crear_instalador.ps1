param([string]$Compilador = '', [switch]$Reconstruir, [string]$Python = 'python',
      [string]$Conexion = 'datos/supabase.json')
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    if ($Reconstruir) {
        & (Join-Path $PSScriptRoot 'empaquetar.ps1')
    }
    if (-not (Test-Path -LiteralPath 'dist/FraseYa/FraseYa.exe')) {
        throw 'Genera el portable primero o utiliza -Reconstruir.'
    }
    if (-not $Compilador) {
        $enRuta = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($enRuta) { $Compilador = $enRuta.Source }
        else {
            foreach ($candidato in @(
                '.test-temp/inno/ISCC.exe',
                'C:/Program Files (x86)/Inno Setup 6/ISCC.exe',
                'C:/Program Files/Inno Setup 6/ISCC.exe')) {
                if (Test-Path -LiteralPath $candidato) { $Compilador = $candidato; break }
            }
        }
    }
    if (-not $Compilador) { throw 'Instala Inno Setup o indica -Compilador con la ruta a ISCC.exe.' }
    $conexionPreparada = Join-Path (Get-Location).Path '.test-temp/config-instalador/supabase.json'
    # No copiar el archivo local entero: podría contener campos personales.
    & $Python 'scripts/preparar_conexion_instalador.py' $Conexion $conexionPreparada
    if ($LASTEXITCODE -ne 0) { throw 'La conexión pública no es válida; no se genera el instalador.' }
    & $Compilador ('/DConfigPublica=' + $conexionPreparada) 'instalador/FraseYa.iss'
    if ($LASTEXITCODE -ne 0) { throw 'Falló la creación del instalador.' }
    Get-FileHash -LiteralPath 'dist/FraseYa-Instalador.exe' -Algorithm SHA256
} finally { Pop-Location }
