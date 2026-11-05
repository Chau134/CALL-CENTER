# Power BI implementation assets

## Files

- `call_center_wfm_theme.json`: import bằng **View → Themes → Browse for themes**.
- `measures.dax`: measure library đã khớp schema PostgreSQL hiện tại.
- `../docs/power_bi_dashboard_plan.md`: relationships, page layout và QA checklist.
- `../sql/04_powerbi_model_qa.sql`: SQL kiểm tra model readiness.

## Thứ tự thao tác trong Power BI Desktop

1. Kết nối `localhost:5432`, database `call_center_wfm`, mode Import.
2. Import 4 dimensions, 5 facts và `vw_powerbi_refresh_status` theo kế hoạch.
3. Tạo relationships `1:*`, single direction.
4. Mark `dim_date[calendar_date]` là Date Table và cấu hình sort columns.
5. Import theme JSON.
6. Tạo table `_Measures` bằng **Enter data**, sau đó tạo từng measure từ `measures.dax` và đặt Home table là `_Measures`.
7. Đối soát năm KPI Executive trước khi tạo visual còn lại.
8. Dựng ba pages theo kế hoạch và hoàn thành cross-layer QA.

Power BI Desktop không hỗ trợ import trực tiếp một file DAX chứa nhiều measures nếu không có external tool. File `measures.dax` là nguồn copy/paste có kiểm soát; không chạy toàn bộ file như một DAX query.

## Formatting

- Calls, intervals, agents: whole number, thousand separator.
- Rates/WAPE/Bias: percentage, 2 decimals.
- AHT/wait: decimal seconds hoặc `mm:ss`, dùng nhất quán.
- Workload/agent-hours: decimal, 2 digits.
- Last Warehouse Load: date/time.
