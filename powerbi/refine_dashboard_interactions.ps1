param(
    [string]$ProjectRoot = "C:\A\CALL-CENTER\powerbi"
)

$ErrorActionPreference = "Stop"
$reportRoot = Join-Path $ProjectRoot "call_center_wfm.Report"
$pagesRoot = Join-Path $reportRoot "definition\pages"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (-not (Test-Path -LiteralPath $pagesRoot)) {
    throw "PBIR pages folder not found: $pagesRoot"
}

function Write-JsonFile {
    param([string]$Path, $Value)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $json = $Value | ConvertTo-Json -Depth 60
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, $utf8NoBom)
}

function Set-JsonProperty {
    param($Object, [string]$Name, $Value)
    if ($null -ne $Object.PSObject.Properties[$Name]) {
        $Object.$Name = $Value
    }
    else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function New-Literal {
    param([string]$Value)
    return [ordered]@{
        expr = [ordered]@{
            Literal = [ordered]@{ Value = $Value }
        }
    }
}

function New-Fill {
    param([string]$Color)
    return [ordered]@{
        solid = [ordered]@{
            color = New-Literal "'$Color'"
        }
    }
}

function Get-VisualPath {
    param([string]$PageId, [string]$VisualName)
    return Join-Path $pagesRoot "$PageId\visuals\$VisualName\visual.json"
}

function Update-Visual {
    param([string]$PageId, [string]$VisualName, [scriptblock]$Update)
    $path = Get-VisualPath $PageId $VisualName
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Visual not found: $PageId/$VisualName"
    }
    $doc = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    & $Update $doc
    Write-JsonFile -Path $path -Value $doc
}

function Ensure-VisualObjects {
    param($Doc)
    if ($null -eq $Doc.visual.objects) {
        Set-JsonProperty -Object $Doc.visual -Name "objects" -Value ([pscustomobject]@{})
    }
    return $Doc.visual.objects
}

function Ensure-VisualContainerObjects {
    param($Doc)
    if ($null -eq $Doc.visual.visualContainerObjects) {
        Set-JsonProperty -Object $Doc.visual -Name "visualContainerObjects" -Value ([pscustomobject]@{})
    }
    return $Doc.visual.visualContainerObjects
}

function Set-DropdownSlicer {
    param([string]$PageId, [string]$VisualName)
    Update-Visual $PageId $VisualName {
        param($doc)
        $objects = Ensure-VisualObjects $doc
        $data = @(
            [ordered]@{
                properties = [ordered]@{
                    mode = New-Literal "'Dropdown'"
                }
            }
        )
        Set-JsonProperty -Object $objects -Name "data" -Value $data
    }
}

function Set-DateSlicerBetween {
    param([string]$PageId, [string]$VisualName)
    Update-Visual $PageId $VisualName {
        param($doc)
        $objects = Ensure-VisualObjects $doc
        $data = @(
            [ordered]@{
                properties = [ordered]@{
                    mode = New-Literal "'Between'"
                }
            }
        )
        Set-JsonProperty -Object $objects -Name "data" -Value $data
    }
}

function Set-HeatmapGradient {
    param(
        [string]$PageId,
        [string]$VisualName,
        [string]$QueryRef,
        [string]$MinColor = "#DCECF7",
        [string]$MaxColor = "#1F4E78"
    )

    Update-Visual $PageId $VisualName {
        param($doc)
        $objects = Ensure-VisualObjects $doc
        $gradient = @(
            [ordered]@{
                properties = [ordered]@{
                    backColor = [ordered]@{
                        solid = [ordered]@{
                            color = [ordered]@{
                                expr = [ordered]@{
                                    FillRule = [ordered]@{
                                        Input = [ordered]@{
                                            SelectRef = [ordered]@{ ExpressionName = $QueryRef }
                                        }
                                        FillRule = [ordered]@{
                                            linearGradient2 = [ordered]@{
                                                min = [ordered]@{
                                                    color = [ordered]@{
                                                        Literal = [ordered]@{ Value = "'$MinColor'" }
                                                    }
                                                }
                                                max = [ordered]@{
                                                    color = [ordered]@{
                                                        Literal = [ordered]@{ Value = "'$MaxColor'" }
                                                    }
                                                }
                                                nullColoringStrategy = [ordered]@{
                                                    strategy = [ordered]@{
                                                        Literal = [ordered]@{ Value = "'noColor'" }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                selector = [ordered]@{
                    data = @(
                        [ordered]@{
                            dataViewWildcard = [ordered]@{ matchingOption = 1 }
                        }
                    )
                    metadata = $QueryRef
                }
            }
        )
        Set-JsonProperty -Object $objects -Name "values" -Value $gradient

        $vco = Ensure-VisualContainerObjects $doc
        $stylePreset = @(
            [ordered]@{
                properties = [ordered]@{
                    name = New-Literal "'None'"
                }
            }
        )
        Set-JsonProperty -Object $vco -Name "stylePreset" -Value $stylePreset
    }
}

function Add-AhtProxyTooltip {
    param([string]$PageId, [string]$VisualName)

    $tooltipText = "AHT Proxy = total service_seconds / valid answered calls. Source data has no hold time or after-call work (ACW), so this is not full operational AHT."
    Update-Visual $PageId $VisualName {
        param($doc)
        $vco = Ensure-VisualContainerObjects $doc
        $visualHeader = @(
            [ordered]@{
                properties = [ordered]@{
                    show = New-Literal "true"
                    showTooltipButton = New-Literal "true"
                }
            }
        )
        $visualHeaderTooltip = @(
            [ordered]@{
                properties = [ordered]@{
                    type = New-Literal "'Default'"
                    text = New-Literal "'$tooltipText'"
                }
            }
        )
        Set-JsonProperty -Object $vco -Name "visualHeader" -Value $visualHeader
        Set-JsonProperty -Object $vco -Name "visualHeaderTooltip" -Value $visualHeaderTooltip
    }
}

function Set-LayoutBand {
    param([string]$PageId)

    $visualsPath = Join-Path $pagesRoot "$PageId\visuals"
    Get-ChildItem -LiteralPath $visualsPath -Directory | ForEach-Object {
        $path = Join-Path $_.FullName "visual.json"
        $doc = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
        switch ([int]$doc.position.y) {
            24 {
                $doc.position.y = 66
                $doc.position.height = 76
            }
            126 {
                $doc.position.y = 158
                $doc.position.height = 150
            }
            320 {
                $doc.position.y = 324
                $doc.position.height = 320
            }
            674 {
                $doc.position.y = 660
                $doc.position.height = 390
            }
        }
        Write-JsonFile -Path $path -Value $doc
    }
}

function New-ActionButton {
    param(
        [string]$PageId,
        [string]$Name,
        [string]$Label,
        [double]$X,
        [double]$Width,
        [int]$Z,
        [string]$ActionType,
        [string]$TargetPageId,
        [string]$Tooltip,
        [string]$FillColor,
        [string]$HoverColor
    )

    $linkProperties = [ordered]@{
        show = New-Literal "true"
        type = New-Literal "'$ActionType'"
        tooltip = New-Literal "'$Tooltip'"
    }
    if ($ActionType -eq "PageNavigation") {
        $linkProperties.navigationSection = New-Literal "'$TargetPageId'"
    }

    $button = [ordered]@{
        '$schema' = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"
        name = $Name
        position = [ordered]@{
            x = $X
            y = 8
            z = $Z
            height = 44
            width = $Width
            tabOrder = $Z
        }
        visual = [ordered]@{
            visualType = "actionButton"
            objects = [ordered]@{
                text = @(
                    [ordered]@{ properties = [ordered]@{ show = New-Literal "true" } },
                    [ordered]@{
                        properties = [ordered]@{
                            text = New-Literal "'$Label'"
                            fontSize = New-Literal "11D"
                            fontColor = New-Fill "#FFFFFF"
                            horizontalAlignment = New-Literal "'center'"
                        }
                        selector = [ordered]@{ id = "default" }
                    }
                )
                icon = @(
                    [ordered]@{ properties = [ordered]@{ show = New-Literal "false" } },
                    [ordered]@{
                        properties = [ordered]@{
                            shapeType = New-Literal "'blank'"
                            placement = New-Literal "'left'"
                        }
                        selector = [ordered]@{ id = "default" }
                    }
                )
                fill = @(
                    [ordered]@{ properties = [ordered]@{ show = New-Literal "true" } },
                    [ordered]@{
                        properties = [ordered]@{ fillColor = New-Fill $FillColor }
                        selector = [ordered]@{ id = "default" }
                    },
                    [ordered]@{
                        properties = [ordered]@{ fillColor = New-Fill $HoverColor }
                        selector = [ordered]@{ id = "hover" }
                    }
                )
                outline = @(
                    [ordered]@{ properties = [ordered]@{ show = New-Literal "false" } }
                )
                shape = @(
                    [ordered]@{
                        properties = [ordered]@{
                            tileShape = New-Literal "'rectangleRounded'"
                            roundEdge = New-Literal "8L"
                        }
                    },
                    [ordered]@{
                        properties = [ordered]@{ tileShape = New-Literal "'rectangleRounded'" }
                        selector = [ordered]@{ id = "default" }
                    }
                )
            }
            visualContainerObjects = [ordered]@{
                background = @(
                    [ordered]@{ properties = [ordered]@{ show = New-Literal "false" } }
                )
                border = @(
                    [ordered]@{ properties = [ordered]@{ show = New-Literal "false" } }
                )
                visualLink = @(
                    [ordered]@{ properties = $linkProperties }
                )
            }
            drillFilterOtherVisuals = $true
        }
        howCreated = "InsertVisualButton"
    }

    $path = Get-VisualPath $PageId $Name
    Write-JsonFile -Path $path -Value $button
}

$pages = [ordered]@{
    overview = "0018c160c18e2ab57782"
    forecast = "f2a9c710d3e84b56a201"
    service = "c3b8d620e4f95a67b302"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $ProjectRoot "backups"
$backupPath = Join-Path $backupRoot "call_center_wfm.Report_before_interactions_$timestamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
Copy-Item -LiteralPath $reportRoot -Destination $backupPath -Recurse

foreach ($pageId in $pages.Values) {
    Set-LayoutBand -PageId $pageId
}

Set-DateSlicerBetween $pages.overview "slicer_date"
@("slicer_queue", "slicer_day", "slicer_daypart", "slicer_holiday") | ForEach-Object {
    Set-DropdownSlicer $pages.overview $_
}

Set-DateSlicerBetween $pages.forecast "slicer_target_date"
@("slicer_model", "slicer_fold", "slicer_scope", "slicer_queue") | ForEach-Object {
    Set-DropdownSlicer $pages.forecast $_
}

Set-DateSlicerBetween $pages.service "slicer_date"
@("slicer_queue", "slicer_service_type", "slicer_coverage") | ForEach-Object {
    Set-DropdownSlicer $pages.service $_
}

Set-HeatmapGradient $pages.overview "intraday_heatmap" "_Measures.Agent Demand Calls" "#DCECF7" "#1F4E78"
Set-HeatmapGradient $pages.forecast "staffing_heatmap" "_Measures.Peak Scheduled Agents" "#FCE7D2" "#F28E2B"
Set-HeatmapGradient $pages.service "service_interval_heatmap" "_Measures.Service Agent Demand Calls" "#D7EFEB" "#2A9D8F"

Add-AhtProxyTooltip $pages.overview "kpi_summary"
Add-AhtProxyTooltip $pages.service "service_kpi_summary"
Add-AhtProxyTooltip $pages.service "service_aht"

$pageSpecs = @(
    [ordered]@{ key = "overview"; id = $pages.overview },
    [ordered]@{ key = "forecast"; id = $pages.forecast },
    [ordered]@{ key = "service"; id = $pages.service }
)

foreach ($source in $pageSpecs) {
    $active = "#F28E2B"
    $inactive = "#1F4E78"

    New-ActionButton $source.id "nav_overview" "Overview" 30 190 40000 "PageNavigation" $pages.overview "Go to Executive Overview" $(if ($source.key -eq "overview") { $active } else { $inactive }) "#163A5F"
    New-ActionButton $source.id "nav_forecast" "Forecast & Staffing" 234 240 41000 "PageNavigation" $pages.forecast "Go to Forecast & Staffing" $(if ($source.key -eq "forecast") { $active } else { $inactive }) "#163A5F"
    New-ActionButton $source.id "nav_service" "Service & Data Quality" 488 260 42000 "PageNavigation" $pages.service "Go to Service Mix & Data Quality" $(if ($source.key -eq "service") { $active } else { $inactive }) "#163A5F"
    New-ActionButton $source.id "reset_filters" "Reset Filters" 1716 160 43000 "ClearAllSlicers" "" "Clear all slicer selections on this page" "#6B7280" "#4B5563"
}

Write-Output "backup_path=$backupPath"
Write-Output "dropdown_slicers=11"
Write-Output "date_slicers_between=3"
Write-Output "heatmaps=3"
Write-Output "aht_tooltips=3"
Write-Output "navigation_buttons=9"
Write-Output "reset_buttons=3"
