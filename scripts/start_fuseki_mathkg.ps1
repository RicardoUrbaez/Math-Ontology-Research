param(
    [string]$FusekiHome = "C:\Users\Ricardo\Downloads\apache-jena-fuseki-6.1.0",
    [string]$Dataset = "mathkg500",
    [string]$Ontology = "C:\Users\Ricardo\Documents\Math-Ontology-Research\ontologies\merged\math_accessibility_kg_week3_grouped_for_protege.owl",
    [string]$FusekiBase = "",
    [int]$Port = 3030,
    [switch]$ConfiguredMode
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($FusekiBase)) {
    $localRoot = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $env:TEMP }
    $FusekiBase = Join-Path $localRoot "MathOntoSpeak\fuseki"
}
New-Item -ItemType Directory -Path $FusekiBase -Force | Out-Null
$env:FUSEKI_BASE = $FusekiBase

if (-not (Test-Path -LiteralPath $FusekiHome)) {
    throw "Fuseki folder not found: $FusekiHome"
}

if (-not $ConfiguredMode -and -not (Test-Path -LiteralPath $Ontology)) {
    throw "Ontology file not found: $Ontology"
}

$jar = Join-Path $FusekiHome "fuseki-server.jar"
if (-not (Test-Path -LiteralPath $jar)) {
    throw "Fuseki server jar not found: $jar"
}

Push-Location $FusekiHome
try {
    if (-not $ConfiguredMode) {
        Write-Host "Starting Fuseki on http://localhost:$Port/$Dataset"
        Write-Host "Loading ontology: $Ontology"
        Write-Host "Fuseki state: $FusekiBase"
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
