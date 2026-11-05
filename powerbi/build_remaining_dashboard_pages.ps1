param(
    [string]$ProjectRoot = "C:\A\CALL-CENTER\powerbi"
)

$ErrorActionPreference = "Stop"
$reportRoot = Join-Path $ProjectRoot "call_center_wfm.Report"
$definitionRoot = Join-Path $reportRoot "definition"
$pagesRoot = Join-Path $definitionRoot "pages"
$pagesMetadataPath = Join-Path $pagesRoot "pages.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (-not (Test-Path -LiteralPath $pagesMetadataPath)) {
    throw "PBIR pages metadata not found: $pagesMetadataPath"
}

function Write-JsonFile {
    param([string]$Path, $Value)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $json = $Value | ConvertTo-Json -Depth 40
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, $utf8NoBom)
}

function New-LiteralExpression {
    param([string]$Value)
    return [ordered]@{ expr = [ordered]@{ Literal = [ordered]@{ Value = $Value } } }
}

function New-ColumnProjection {
    param([string]$Entity, [string]$Property, [string]$DisplayName = $Property)
    return [ordered]@{
        field = [ordered]@{
            Column = [ordered]@{
                Expression = [ordered]@{ SourceRef = [ordered]@{ Entity = $Entity } }
                Property = $Property
            }
        }
        queryRef = "$Entity.$Property"
        nativeQueryRef = $DisplayName
    }
}

function New-MeasureProjection {
    param([string]$Property, [string]$DisplayName = $Property)
    return [ordered]@{
        field = [ordered]@{
            Measure = [ordered]@{
                Expression = [ordered]@{ SourceRef = [ordered]@{ Entity = "_Measures" } }
                Property = $Property
            }
        }
        queryRef = "_Measures.$Property"
        nativeQueryRef = $DisplayName
    }
}

function New-VisualDefinition {
    param(
        [string]$Name,
        [string]$VisualType,
        [int]$X,
        [int]$Y,
        [int]$Width,
        [int]$Height,
        [int]$TabOrder,
        [hashtable]$Roles,
        [string]$Title
    )

    $queryState = [ordered]@{}
    foreach ($roleName in $Roles.Keys) {
        $queryState[$roleName] = [ordered]@{ projections = @($Roles[$roleName]) }
    }

    return [ordered]@{
        '$schema' = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"
        name = $Name
        position = [ordered]@{
            x = $X; y = $Y; z = 1000 + $TabOrder
            height = $Height; width = $Width; tabOrder = $TabOrder
        }
        visual = [ordered]@{
            visualType = $VisualType
            query = [ordered]@{ queryState = $queryState }
            visualContainerObjects = [ordered]@{
                title = @(
                    [ordered]@{
                        properties = [ordered]@{
                            show = New-LiteralExpression -Value "true"
                            text = New-LiteralExpression -Value "'$Title'"
                        }
                    }
                )
            }
            drillFilterOtherVisuals = $true
        }
        annotations = @(
            [ordered]@{ name = "CALL_CENTER_WFM_AUTOGEN"; value = "1.0.0" }
        )
    }
}

function Initialize-Page {
    param([string]$PageName, [string]$DisplayName)
    $pageRoot = Join-Path $pagesRoot $PageName
    $pagePath = Join-Path $pageRoot "page.json"
    $visualsRoot = Join-Path $pageRoot "visuals"
    if (-not (Test-Path -LiteralPath $visualsRoot)) {
        New-Item -ItemType Directory -Path $visualsRoot -Force | Out-Null
    }
    $page = [ordered]@{
        '$schema' = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
        name = $PageName
        displayName = $DisplayName
        displayOption = "FitToPage"
        height = 1080
        width = 1920
        annotations = @(
            [ordered]@{ name = "CALL_CENTER_WFM_AUTOGEN"; value = "1.0.0" }
        )
    }
    Write-JsonFile -Path $pagePath -Value $page
    return $visualsRoot
}

function Write-Visual {
    param([string]$VisualsRoot, $Definition)
    $path = Join-Path (Join-Path $VisualsRoot $Definition.name) "visual.json"
    Write-JsonFile -Path $path -Value $Definition
}

$backupRoot = Join-Path $ProjectRoot "backups"
if (-not (Test-Path -LiteralPath $backupRoot)) {
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
}
$backupPath = Join-Path $backupRoot ("call_center_wfm.Report_before_pages_2_3_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
Copy-Item -LiteralPath $reportRoot -Destination $backupPath -Recurse

$forecastPageName = "f2a9c710d3e84b56a201"
$servicePageName = "c3b8d620e4f95a67b302"

# Page 2: Forecast & Staffing
$forecastVisualsRoot = Initialize-Page -PageName $forecastPageName -DisplayName "02 Forecast & Staffing"
$forecastVisuals = @()
$tabOrder = 0

$forecastSlicers = @(
    @{ Name = "slicer_model"; X = 30; Entity = "fact_model_evaluation"; Property = "model_name"; Title = "Model" },
    @{ Name = "slicer_fold"; X = 404; Entity = "fact_model_evaluation"; Property = "backtest_fold"; Title = "Backtest fold" },
    @{ Name = "slicer_scope"; X = 778; Entity = "fact_model_evaluation"; Property = "evaluation_scope"; Title = "Evaluation scope" },
    @{ Name = "slicer_target_date"; X = 1152; Entity = "dim_date"; Property = "calendar_date"; Title = "Target date" },
    @{ Name = "slicer_queue"; X = 1526; Entity = "dim_queue"; Property = "queue_name"; Title = "Queue" }
)
foreach ($spec in $forecastSlicers) {
    $roles = @{ Values = @((New-ColumnProjection -Entity $spec.Entity -Property $spec.Property)) }
    $forecastVisuals += New-VisualDefinition -Name $spec.Name -VisualType "slicer" -X $spec.X -Y 24 -Width 350 -Height 82 -TabOrder $tabOrder -Roles $roles -Title $spec.Title
    $tabOrder++
}

$forecastKpis = @{
    Data = @(
        (New-MeasureProjection -Property "Selected Model Name"),
        (New-MeasureProjection -Property "Selected Forecast WAPE"),
        (New-MeasureProjection -Property "Selected Forecast Bias"),
        (New-MeasureProjection -Property "Selected Forecast MAE"),
        (New-MeasureProjection -Property "Selected Forecast RMSE")
    )
}
$forecastVisuals += New-VisualDefinition -Name "forecast_kpi_summary" -VisualType "cardVisual" -X 30 -Y 126 -Width 1846 -Height 170 -TabOrder $tabOrder -Roles $forecastKpis -Title "Selected Forecast Model"
$tabOrder++

$modelComparisonRoles = @{
    Category = @((New-ColumnProjection -Entity "fact_model_evaluation" -Property "model_name" -DisplayName "Model"))
    Y = @((New-MeasureProjection -Property "Model WAPE (All Folds)" -DisplayName "WAPE"))
}
$forecastVisuals += New-VisualDefinition -Name "model_comparison" -VisualType "clusteredBarChart" -X 30 -Y 320 -Width 600 -Height 330 -TabOrder $tabOrder -Roles $modelComparisonRoles -Title "Model Comparison - WAPE"
$tabOrder++

$actualForecastRoles = @{
    Category = @((New-ColumnProjection -Entity "fact_forecast_interval" -Property "target_local_interval_start" -DisplayName "Target interval"))
    Y = @(
        (New-MeasureProjection -Property "Selected Forecast Actual" -DisplayName "Actual"),
        (New-MeasureProjection -Property "Selected Forecast Calls" -DisplayName "Forecast")
    )
}
$forecastVisuals += New-VisualDefinition -Name "actual_vs_forecast" -VisualType "lineChart" -X 654 -Y 320 -Width 1222 -Height 330 -TabOrder $tabOrder -Roles $actualForecastRoles -Title "Actual vs Selected Forecast"
$tabOrder++

$staffingRoles = @{
    Category = @((New-ColumnProjection -Entity "fact_staffing_requirement" -Property "target_local_interval_start" -DisplayName "Target interval"))
    Y = @(
        (New-MeasureProjection -Property "Peak Productive Agents" -DisplayName "Productive agents"),
        (New-MeasureProjection -Property "Peak Scheduled Agents" -DisplayName "Scheduled agents")
    )
}
$forecastVisuals += New-VisualDefinition -Name "staffing_requirement" -VisualType "lineChart" -X 30 -Y 674 -Width 910 -Height 376 -TabOrder $tabOrder -Roles $staffingRoles -Title "Productive vs Scheduled Staffing Requirement"
$tabOrder++

$staffingHeatmapRoles = @{
    Rows = @((New-ColumnProjection -Entity "dim_date" -Property "day_name" -DisplayName "Day"))
    Columns = @((New-ColumnProjection -Entity "dim_time_interval" -Property "start_time" -DisplayName "Interval"))
    Values = @((New-MeasureProjection -Property "Peak Scheduled Agents" -DisplayName "Scheduled agents"))
}
$forecastVisuals += New-VisualDefinition -Name "staffing_heatmap" -VisualType "pivotTable" -X 966 -Y 674 -Width 910 -Height 376 -TabOrder $tabOrder -Roles $staffingHeatmapRoles -Title "Scheduled Staffing Heatmap"

foreach ($visual in $forecastVisuals) {
    Write-Visual -VisualsRoot $forecastVisualsRoot -Definition $visual
}

# Page 3: Service Mix & Data Quality
$serviceVisualsRoot = Initialize-Page -PageName $servicePageName -DisplayName "03 Service Mix & Data Quality"
$serviceVisuals = @()
$tabOrder = 0

$serviceSlicers = @(
    @{ Name = "slicer_date"; X = 30; Entity = "dim_date"; Property = "calendar_date"; Title = "Date" },
    @{ Name = "slicer_queue"; X = 498; Entity = "dim_queue"; Property = "queue_name"; Title = "Queue" },
    @{ Name = "slicer_service_type"; X = 966; Entity = "dim_service_type"; Property = "service_type_name"; Title = "Service type" },
    @{ Name = "slicer_coverage"; X = 1434; Entity = "fact_service_type_interval"; Property = "coverage_status"; Title = "Coverage status" }
)
foreach ($spec in $serviceSlicers) {
    $roles = @{ Values = @((New-ColumnProjection -Entity $spec.Entity -Property $spec.Property)) }
    $serviceVisuals += New-VisualDefinition -Name $spec.Name -VisualType "slicer" -X $spec.X -Y 24 -Width 442 -Height 82 -TabOrder $tabOrder -Roles $roles -Title $spec.Title
    $tabOrder++
}

$serviceKpis = @{
    Data = @(
        (New-MeasureProjection -Property "Service Offered Calls"),
        (New-MeasureProjection -Property "Service Answer Rate"),
        (New-MeasureProjection -Property "Service Abandon Rate"),
        (New-MeasureProjection -Property "Service AHT Proxy Seconds" -DisplayName "Service AHT Proxy (seconds)"),
        (New-MeasureProjection -Property "Last Warehouse Load")
    )
}
$serviceVisuals += New-VisualDefinition -Name "service_kpi_summary" -VisualType "cardVisual" -X 30 -Y 126 -Width 1846 -Height 170 -TabOrder $tabOrder -Roles $serviceKpis -Title "Service Mix KPI Summary"
$tabOrder++

$serviceVolumeRoles = @{
    Category = @((New-ColumnProjection -Entity "dim_service_type" -Property "service_type_name" -DisplayName "Service type"))
    Y = @((New-MeasureProjection -Property "Service Offered Calls" -DisplayName "Offered calls"))
}
$serviceVisuals += New-VisualDefinition -Name "service_volume" -VisualType "clusteredColumnChart" -X 30 -Y 320 -Width 600 -Height 330 -TabOrder $tabOrder -Roles $serviceVolumeRoles -Title "Offered Calls by Service Type"
$tabOrder++

$serviceRateRoles = @{
    Category = @((New-ColumnProjection -Entity "dim_service_type" -Property "service_type_name" -DisplayName "Service type"))
    Y = @(
        (New-MeasureProjection -Property "Service Answer Rate" -DisplayName "Answer rate"),
        (New-MeasureProjection -Property "Service Abandon Rate" -DisplayName "Abandon rate")
    )
}
$serviceVisuals += New-VisualDefinition -Name "service_rates" -VisualType "clusteredColumnChart" -X 654 -Y 320 -Width 600 -Height 330 -TabOrder $tabOrder -Roles $serviceRateRoles -Title "Answer and Abandon Rate by Service Type"
$tabOrder++

$serviceAhtRoles = @{
    Category = @((New-ColumnProjection -Entity "dim_service_type" -Property "service_type_name" -DisplayName "Service type"))
    Y = @((New-MeasureProjection -Property "Service AHT Proxy Seconds" -DisplayName "AHT proxy (seconds)"))
}
$serviceVisuals += New-VisualDefinition -Name "service_aht" -VisualType "clusteredBarChart" -X 1278 -Y 320 -Width 598 -Height 330 -TabOrder $tabOrder -Roles $serviceAhtRoles -Title "AHT Proxy by Service Type"
$tabOrder++

$serviceHeatmapRoles = @{
    Rows = @((New-ColumnProjection -Entity "dim_service_type" -Property "service_type_name" -DisplayName "Service type"))
    Columns = @((New-ColumnProjection -Entity "dim_time_interval" -Property "start_time" -DisplayName "Interval"))
    Values = @((New-MeasureProjection -Property "Service Agent Demand Calls" -DisplayName "Agent demand"))
}
$serviceVisuals += New-VisualDefinition -Name "service_interval_heatmap" -VisualType "pivotTable" -X 30 -Y 674 -Width 1224 -Height 376 -TabOrder $tabOrder -Roles $serviceHeatmapRoles -Title "Service Type by Interval Demand"
$tabOrder++

$coverageRoles = @{
    Category = @((New-ColumnProjection -Entity "fact_service_type_interval" -Property "coverage_status" -DisplayName "Coverage status"))
    Y = @((New-MeasureProjection -Property "Service Offered Calls" -DisplayName "Offered calls"))
}
$serviceVisuals += New-VisualDefinition -Name "coverage_status" -VisualType "clusteredBarChart" -X 1278 -Y 674 -Width 598 -Height 376 -TabOrder $tabOrder -Roles $coverageRoles -Title "Coverage Status"

foreach ($visual in $serviceVisuals) {
    Write-Visual -VisualsRoot $serviceVisualsRoot -Definition $visual
}

$pagesMetadata = Get-Content -LiteralPath $pagesMetadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
$existingOrder = @($pagesMetadata.pageOrder | Where-Object { $_ -notin @($forecastPageName, $servicePageName) })
$pagesMetadata.pageOrder = @($existingOrder + $forecastPageName + $servicePageName)
Write-JsonFile -Path $pagesMetadataPath -Value $pagesMetadata

Write-Output "backup_path=$backupPath"
Write-Output "forecast_page=$forecastPageName"
Write-Output "forecast_visuals=$($forecastVisuals.Count)"
Write-Output "service_page=$servicePageName"
Write-Output "service_visuals=$($serviceVisuals.Count)"
