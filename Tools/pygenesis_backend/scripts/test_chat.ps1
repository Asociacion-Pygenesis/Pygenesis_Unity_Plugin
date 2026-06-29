# Prueba GET /chat/capabilities y POST /chat con cuerpo UTF-8 (compatible con Windows PowerShell 5.x).
# Uso: desde Tools\pygenesis_backend:  powershell -File .\scripts\test_chat.ps1

$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8765"

Write-Host "GET $base/chat/capabilities"
Invoke-RestMethod -Uri "$base/chat/capabilities" -Method Get | ConvertTo-Json -Depth 6

# Importante: el body debe ir en UTF-8 bytes. Un string en -Body solo a veces usa UTF-16 y FastAPI no parsea el JSON.
$json = '{"messages":[{"role":"user","content":"Hola, que puedes hacer?"}]}'
$utf8 = New-Object System.Text.UTF8Encoding $false

Write-Host "`nPOST $base/chat"
Invoke-RestMethod -Uri "$base/chat" -Method Post -ContentType "application/json; charset=utf-8" -Body $utf8.GetBytes($json) | ConvertTo-Json -Depth 4
