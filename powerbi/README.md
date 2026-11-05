# Power BI implementation assets

## Files

- `call_center_wfm_theme.json`: import bằng **Design → Import theme** trong Power BI Desktop ribbon mới.
- `measures.dax`: measure library đã khớp schema PostgreSQL hiện tại.
- `setup_model.csx`: Tabular Editor 2 script tạo/update measures, formatting, sort và ẩn technical columns.
- `setup_relationships.csx`: sửa/đảm bảo hai relationship Service Type theo star schema đã chốt.
- `build_executive_overview.ps1`: tạo page Executive Overview và 9 PBIR visuals.
- `build_remaining_dashboard_pages.ps1`: tạo hai pages Forecast/Staffing và Service Mix/Data Quality với 20 PBIR visuals.
- `refine_dashboard_interactions.ps1`: thêm dropdown slicers, heatmap gradients, AHT Proxy tooltip, page navigation và Reset Filters.
- `call_center_wfm.pbip`: Power BI Project chính; report dùng PBIR và semantic model dùng TMDL.
- `../docs/power_bi_dashboard_plan.md`: relationships, page layout và QA checklist.
- `../sql/04_powerbi_model_qa.sql`: SQL kiểm tra model readiness.

## Thứ tự thao tác trong Power BI Desktop

1. Kết nối `localhost:5432`, database `call_center_wfm`, mode Import.
2. Import 4 dimensions, 5 facts và `vw_powerbi_refresh_status` theo kế hoạch.
3. Chạy `setup_model.csx`, sau đó `setup_relationships.csx` để tạo semantic model và hoàn thiện relationships `1:*`, single direction.
4. Mark `dim_date[calendar_date]` là Date Table và cấu hình sort columns.
5. Import theme JSON.
6. Đối soát năm KPI Executive; `measures.dax` là bản tham chiếu để review/copy thủ công khi cần.
7. Save As Power BI Project `call_center_wfm.pbip`.
8. Chạy ba PBIR scripts, áp dụng external changes trong Desktop và hoàn thành cross-layer QA.

Power BI Desktop không hỗ trợ import trực tiếp một file DAX chứa nhiều measures nếu không có external tool. File `measures.dax` là nguồn copy/paste có kiểm soát; không chạy toàn bộ file như một DAX query.

## Chạy Tabular Editor 2 sau khi PBIX đã import tables

Giữ đúng một Power BI Desktop model đang mở, sau đó chạy từ PowerShell:

```powershell
$te = 'C:\Program Files (x86)\Tabular Editor\TabularEditor.exe'
$script = 'C:\A\CALL-CENTER\powerbi\setup_model.csx'
$relationshipScript = 'C:\A\CALL-CENTER\powerbi\setup_relationships.csx'
$backup = 'C:\A\CALL-CENTER\powerbi\model_before_setup.bim'

Start-Process -FilePath $te -Wait -NoNewWindow -ArgumentList @('-L', '-B', $backup)
Start-Process -FilePath $te -Wait -NoNewWindow -ArgumentList @('-L', '-S', $script, '-D')
Start-Process -FilePath $te -Wait -NoNewWindow -ArgumentList @('-L', '-S', $relationshipScript, '-D')
```

Lệnh đầu lưu backup metadata; hai lệnh sau áp dụng scripts và ghi metadata trở lại model Power BI đang mở. Script dừng nếu thiếu bất kỳ table bắt buộc nào. Sau khi chạy, lưu PBIX bằng `Ctrl+S`.

Trong **File → Options and settings → Options → Current File → Data Load**, bỏ chọn **Auto date/time** vì model đã có `dim_date`. Cấu hình này loại các `LocalDateTable_*` ẩn và tránh hierarchy ngày trùng lặp.

## Tái tạo report pages trong PBIP

Đóng Power BI Desktop hoặc lưu toàn bộ thay đổi trước khi chạy:

```powershell
& 'C:\A\CALL-CENTER\powerbi\build_executive_overview.ps1'
& 'C:\A\CALL-CENTER\powerbi\build_remaining_dashboard_pages.ps1'
& 'C:\A\CALL-CENTER\powerbi\refine_dashboard_interactions.ps1'
```

Scripts tạo backup report definition trong `powerbi/backups/`, dùng UTF-8 không BOM và có thể chạy lại. Nếu project đang mở, chọn **Apply external changes**, kiểm tra ba pages rồi lưu project.

## Formatting

- Calls, intervals, agents: whole number, thousand separator.
- Rates/WAPE/Bias: percentage, 2 decimals.
- AHT/wait: decimal seconds hoặc `mm:ss`, dùng nhất quán.
- Workload/agent-hours: decimal, 2 digits.
- Last Warehouse Load: date/time.
