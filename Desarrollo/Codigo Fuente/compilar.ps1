# Compila Plan Material Shift.exe en Windows (Python 3.12) y arma la carpeta de entrega.
# Uso (desde esta carpeta):  powershell -ExecutionPolicy Bypass -File compilar.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean "Plan Material Shift.spec"
& (Join-Path $PSScriptRoot "armar_entrega.ps1")
