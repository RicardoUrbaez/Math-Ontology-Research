param(
    [string]$Dataset = "mathkg500",
    [string]$Ontology = "C:\Users\Ricardo\Documents\Math-Ontology-Research\reports\reasoning\math_accessibility_kg_week3_clean.ttl",
    [int]$Port = 3030
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Ontology)) {
    throw "Ontology file not found: $Ontology"
}

$uri = "http://localhost:$Port/$Dataset/data?default"
Write-Host "Loading $Ontology into $uri"
$response = Invoke-RestMethod -Uri $uri -Method Post -ContentType "text/turtle" -InFile $Ontology
$response

