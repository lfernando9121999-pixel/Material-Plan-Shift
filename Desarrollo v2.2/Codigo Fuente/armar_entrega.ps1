# Arma la carpeta de entrega «Plan Material Shift v2.2» en la raíz del repositorio a partir de dist\.
# Uso (desde la raíz del repositorio):  powershell -ExecutionPolicy Bypass -File "Desarrollo v2.2\Codigo Fuente\armar_entrega.ps1"
$ErrorActionPreference = "Stop"
$src  = Join-Path $PSScriptRoot "dist\Plan Material Shift"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$dst  = Join-Path $root "Plan Material Shift v2.2"
if (-not (Test-Path (Join-Path $src "Plan Material Shift.exe"))) { throw "No existe $src. Compile primero con PyInstaller." }
if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
New-Item -ItemType Directory -Path $dst | Out-Null
Copy-Item (Join-Path $src "*") $dst -Recurse
foreach ($d in "Inputs", "Escenarios", "Outputs") {
    New-Item -ItemType Directory -Path (Join-Path $dst $d) -Force | Out-Null
    Copy-Item (Join-Path $PSScriptRoot "entrega\$d\Leame.txt") (Join-Path $dst $d) -Force
}
Copy-Item (Join-Path $PSScriptRoot "entrega\Leame.md") $dst -Force
Write-Host "Entrega lista en $dst"
