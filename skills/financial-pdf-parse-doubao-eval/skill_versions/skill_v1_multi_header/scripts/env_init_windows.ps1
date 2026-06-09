$ErrorActionPreference = "Stop"

Write-Host "[financial-pdf-parse-doubao-eval] Checking Windows PowerShell environment"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "python is not available on PATH"
}

python --version
python -m pip --version | Out-Host
python -m pip install --upgrade las-sdk

if (Get-Command lasutil -ErrorAction SilentlyContinue) {
  lasutil --version
} else {
  Write-Warning "lasutil is not on PATH after las-sdk installation."
}

if (-not $env:LAS_API_KEY) {
  Write-Host 'LAS_API_KEY is not set. Use: $env:LAS_API_KEY="..."'
}
if (-not $env:LAS_REGION) {
  Write-Host 'LAS_REGION is not set. Recommended: $env:LAS_REGION="cn-beijing"'
}

Write-Host "Next steps:"
Write-Host 'python .\scripts\estimate_price.py --input "<PDF_PATH>" --parse-mode detail'
Write-Host 'python .\scripts\run_financial_parse.py --input "<PDF_PATH>" --parse-mode detail --output-dir "<OUTPUT_DIR>" --output-profile standard --yes'
Write-Host "[financial-pdf-parse-doubao-eval] Done. No permanent env vars were modified."
