param(
    [string]$ProjectRoot = "C:\A\CALL-CENTER\powerbi"
)

$ErrorActionPreference = "Stop"

$reportRoot = Join-Path $ProjectRoot "call_center_wfm.Report"
$definitionRoot = Join-Path $reportRoot "definition"
$pagesRoot = Join-Path $definitionRoot "pages"
$pagesMetadataPath = Join-Path $pagesRoot "pages.json"

if (-not (Test-Path -LiteralPath $pagesMetadataPath)) {
    throw "PBIR pages metadata not found: $pagesMetadataPath"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] $Value
    )

    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    $json = $Value | ConvertTo-Json -Depth 40
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, $utf8NoBom)
}

function New-LiteralExpression {
    param([Parameter(Mandatory = $true)] [string]$Value)

    return [ordered]@{
        expr = [ordered]@{
            Literal = [ordered]@{
                Value = $Value
            }
        }
    }
}

function New-ColumnProjection {
    param(
        [Parameter(Mandatory = $true)] [string]$Entity,
        [Parameter(Mandatory = $true)] [string]$Property,
        [string]$DisplayName = $Property
    )

    return [ordered]@{
        field = [ordered]@{
            Column = [ordered]@{
                Expression = [ordered]@{
                    SourceRef = [ordered]@{
                        Entity = $Entity
                    }
                }
                Property = $Property
            }
        }
        queryRef = "$Entity.$Property"
        nativeQueryRef = $DisplayName
    }
}

function New-MeasureProjection {
    param(
        [Parameter(Mandatory = $true)] [string]$Property,
        [string]$DisplayName = $Property
    )

    return [ordered]@{
        field = [ordered]@{
            Measure = [ordered]@{
                Expression = [ordered]@{
                    SourceRef = [ordered]@{
                        Entity = "_Measures"
                    }
                }
                Property = $Property
            }
        }
        queryRef = "_Measures.$Property"
        nativeQueryRef = $DisplayName
    }
}

function New-VisualDefinition {
    param(
        [Parameter(Mandatory = $true)] [string]$Name,
        [Parameter(Mandatory = $true)] [string]$VisualType,
        [Parameter(Mandatory = $true)] [int]$X,
        [Parameter(Mandatory = $true)] [int]$Y,
        [Parameter(Mandatory = $true)] [int]$Width,
        [Parameter(Mandatory = $true)] [int]$Height,
        [Parameter(Mandatory = $true)] [int]$TabOrder,
        [Parameter(Mandatory = $true)] [hashtable]$Roles,
        [Parameter(Mandatory = $true)] [string]$Title
    )

    $queryState = [ordered]@{}
    foreach ($roleName in $Roles.Keys) {
        $queryState[$roleName] = [ordered]@{
            projections = @($Roles[$roleName])
        }
    }

    return [ordered]@{
        '$schema' = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"
        name = $Name
        position = [ordered]@{
            x = $X
            y = $Y
            z = 1000 + $TabOrder
            height = $Height
            width = $Width
            tabOrder = $TabOrder
        }
        visual = [ordered]@{
            visualType = $VisualType
            query = [ordered]@{
                queryState = $queryState
            }
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
            [ordered]@{
                name = "CALL_CENTER_WFM_AUTOGEN"
                value = "1.0.0"
            }
        )
    }
}

function Write-Visual {
    param(
        [Parameter(Mandatory = $true)] [string]$VisualsRoot,
        [Parameter(Mandatory = $true)] $Definition
    )

    $visualPath = Join-Path (Join-Path $VisualsRoot $Definition.name) "visual.json"
    Write-JsonFile -Path $visualPath -Value $Definition
}

$pagesMetadata = Get-Content -LiteralPath $pagesMetadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $pagesMetadata.pageOrder -or $pagesMetadata.pageOrder.Count -lt 1) {
    throw "PBIR contains no page to use for Executive Overview."
}

$pageName = [string]$pagesMetadata.pageOrder[0]
$pageRoot = Join-Path $pagesRoot $pageName
$pagePath = Join-Path $pageRoot "page.json"
$visualsRoot = Join-Path $pageRoot "visuals"

if (-not (Test-Path -LiteralPath $pagePath)) {
    throw "PBIR page definition not found: $pagePath"
}

$backupRoot = Join-Path $ProjectRoot "backups"
if (-not (Test-Path -LiteralPath $backupRoot)) {
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
}
$backupPath = Join-Path $backupRoot ("call_center_wfm.Report_before_executive_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
Copy-Item -LiteralPath $reportRoot -Destination $backupPath -Recurse

$pageDefinition = [ordered]@{
    '$schema' = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
    name = $pageName
    displayName = "01 Executive Overview"
    displayOption = "FitToPage"
    height = 1080
    width = 1920
    annotations = @(
        [ordered]@{
            name = "CALL_CENTER_WFM_AUTOGEN"
            value = "1.0.0"
        }
    )
}
Write-JsonFile -Path $pagePath -Value $pageDefinition

if (-not (Test-Path -LiteralPath $visualsRoot)) {
    New-Item -ItemType Directory -Path $visualsRoot -Force | Out-Null
}

$visuals = @()

$slicerSpecs = @(
    @{ Name = "slicer_date"; X = 30; Entity = "dim_date"; Property = "calendar_date"; Title = "Date" },
    @{ Name = "slicer_queue"; X = 404; Entity = "dim_queue"; Property = "queue_name"; Title = "Queue" },
    @{ Name = "slicer_day"; X = 778; Entity = "dim_date"; Property = "day_name"; Title = "Day of week" },
    @{ Name = "slicer_daypart"; X = 1152; Entity = "dim_time_interval"; Property = "daypart"; Title = "Daypart" },
    @{ Name = "slicer_holiday"; X = 1526; Entity = "dim_date"; Property = "is_holiday"; Title = "Holiday" }
)

$tabOrder = 0
foreach ($spec in $slicerSpecs) {
    $roles = @{
        Values = @(
            New-ColumnProjection -Entity $spec.Entity -Property $spec.Property
        )
    }
    $visuals += New-VisualDefinition -Name $spec.Name -VisualType "slicer" -X $spec.X -Y 24 -Width 350 -Height 82 -TabOrder $tabOrder -Roles $roles -Title $spec.Title
    $tabOrder++
}

$kpiRoles = @{
    Data = @(
        (New-MeasureProjection -Property "Offered Calls"),
        (New-MeasureProjection -Property "Answer Rate"),
        (New-MeasureProjection -Property "Abandon Rate"),
        (New-MeasureProjection -Property "Service Level"),
        (New-MeasureProjection -Property "AHT Proxy Seconds" -DisplayName "AHT Proxy (seconds)")
    )
}
$visuals += New-VisualDefinition -Name "kpi_summary" -VisualType "cardVisual" -X 30 -Y 126 -Width 1846 -Height 170 -TabOrder $tabOrder -Roles $kpiRoles -Title "Executive KPI Summary"
$tabOrder++

$dailyRoles = @{
    Category = @(
        New-ColumnProjection -Entity "dim_date" -Property "calendar_date" -DisplayName "Date"
    )
    Y = @(
        (New-MeasureProjection -Property "Offered Calls"),
        (New-MeasureProjection -Property "Answered Calls"),
        (New-MeasureProjection -Property "Abandoned Calls")
    )
}
$visuals += New-VisualDefinition -Name "daily_traffic" -VisualType "lineChart" -X 30 -Y 320 -Width 910 -Height 330 -TabOrder $tabOrder -Roles $dailyRoles -Title "Daily Traffic"
$tabOrder++

$comboRoles = @{
    Category = @(
        New-ColumnProjection -Entity "dim_date" -Property "calendar_date" -DisplayName "Date"
    )
    Y = @(
        New-MeasureProjection -Property "Offered Calls"
    )
    Y2 = @(
        New-MeasureProjection -Property "Service Level"
    )
}
$visuals += New-VisualDefinition -Name "volume_service_level" -VisualType "lineClusteredColumnComboChart" -X 966 -Y 320 -Width 910 -Height 330 -TabOrder $tabOrder -Roles $comboRoles -Title "Offered Calls vs Service Level"
$tabOrder++

$heatmapRoles = @{
    Rows = @(
        New-ColumnProjection -Entity "dim_date" -Property "day_name" -DisplayName "Day"
    )
    Columns = @(
        New-ColumnProjection -Entity "dim_time_interval" -Property "start_time" -DisplayName "Interval"
    )
    Values = @(
        New-MeasureProjection -Property "Agent Demand Calls"
    )
}
$visuals += New-VisualDefinition -Name "intraday_heatmap" -VisualType "pivotTable" -X 30 -Y 674 -Width 1846 -Height 376 -TabOrder $tabOrder -Roles $heatmapRoles -Title "Intraday Agent Demand Heatmap"

foreach ($visual in $visuals) {
    Write-Visual -VisualsRoot $visualsRoot -Definition $visual
}

$pagesMetadata.activePageName = $pageName
Write-JsonFile -Path $pagesMetadataPath -Value $pagesMetadata

Write-Output "backup_path=$backupPath"
Write-Output "page_name=$pageName"
Write-Output "visual_count=$($visuals.Count)"
