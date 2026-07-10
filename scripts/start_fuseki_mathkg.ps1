param(
    [string]$FusekiHome = "C:\Users\Ricardo\Downloads\apache-jena-fuseki-6.1.0",
    [string]$Dataset = "mathkg500",
    [string]$Ontology = "C:\Users\Ricardo\Documents\Math-Ontology-Research\reports\reasoning\math_accessibility_kg_week3_clean.ttl",
    [int]$Port = 3030,
    [switch]$FileMode
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $FusekiHome)) {
    throw "Fuseki folder not found: $FusekiHome"
}

if ($FileMode -and -not (Test-Path -LiteralPath $Ontology)) {
    throw "Ontology file not found: $Ontology"
}

$jar = Join-Path $FusekiHome "fuseki-server.jar"
if (-not (Test-Path -LiteralPath $jar)) {
    throw "Fuseki server jar not found: $jar"
}

Push-Location $FusekiHome
try {
    if ($FileMode) {
        Write-Host "Starting Fuseki on http://localhost:$Port/$Dataset"
        Write-Host "Loading ontology: $Ontology"
        java -jar $jar --port=$Port --file="$Ontology" "/$Dataset"
    }
    else {
        Write-Host "Starting configured Fuseki server on http://localhost:$Port"
        Write-Host "Expected configured datasets include /mathkg and /mathkg500."
        java -jar $jar --port=$Port
    }
}
finally {
    Pop-Location
}
