# PostgreSQL analytics warehouse và Power BI serving layer

## 1. Trạng thái

Warehouse đã được tạo trong database `call_center_wfm`, schema `analytics` và đã load đủ 9 marts. Lần đối soát gần nhất có 131.544 rows, khớp hoàn toàn với các file trong `data/processed/technion/`.

Loader chạy theo full-snapshot, idempotent và transactional:

1. Tạo tables/indexes nếu chưa tồn tại.
2. `TRUNCATE` đúng 9 mart tables do dự án quản lý.
3. COPY dimensions trước, facts sau.
4. Tạo hoặc refresh KPI views.
5. Ghi row counts và SHA-256 của từng source file vào `analytics.mart_load_audit`.
6. Commit một lần; nếu có lỗi thì rollback toàn bộ lần load.

## 2. Tables và grain

| Table | Grain | Primary key |
|---|---|---|
| `dim_date` | một calendar date | `date_key` |
| `dim_time_interval` | một interval 30 phút | `interval_key` |
| `dim_queue` | một queue | `queue_id` |
| `dim_service_type` | một service type | `service_type_code` |
| `fact_queue_interval_complete` | date × interval × queue | `date_key, interval_key, queue_id` |
| `fact_service_type_interval` | date × interval × service type × queue | `date_key, interval_key, service_type_code, queue_id` |
| `fact_forecast_interval` | forecast run × target interval × queue | `forecast_run_id, target_date_key, target_interval_key, queue_id` |
| `fact_model_evaluation` | model × version × scope × fold | `model_name, model_version, evaluation_scope, backtest_fold` |
| `fact_staffing_requirement` | selected forecast run × target interval × queue | `forecast_run_id, target_date_key, target_interval_key, queue_id` |

Foreign keys ngăn orphan date/interval/queue/service type và bảo đảm staffing requirement tham chiếu đúng selected forecast record. Check constraints khóa các identity như `offered = answered + abandoned`, count không âm, rate trong khoảng hợp lệ và planned forecast phải nằm sau training end.

## 3. KPI/Power BI views

| View | Mục đích |
|---|---|
| `vw_powerbi_queue_interval` | Queue KPIs ở grain 30 phút, đã nối Date/Time/Queue attributes |
| `vw_kpi_daily_queue` | Executive KPI theo ngày/queue |
| `vw_kpi_service_type_daily` | KPI theo ngày/service type |
| `vw_powerbi_forecast_interval` | Actual vs forecast theo model/fold/target interval |
| `vw_kpi_forecast_weekly_model` | WAPE, Bias, MAE, RMSE theo tuần và model |
| `vw_powerbi_model_evaluation` | Kết quả model evaluation theo fold/scope |
| `vw_powerbi_staffing_interval` | Planned requirement và retrospective actualized requirement |
| `vw_kpi_staffing_daily` | Workload và peak/agent-hours requirement theo ngày |
| `vw_powerbi_refresh_status` | Load timestamp, source hashes và row counts |

Tất cả ratio được tính từ tổng tử số chia tổng mẫu số. Không lấy trung bình `answer_rate`, `service_level_rate` hoặc AHT của các interval con.

`vw_powerbi_staffing_interval` chưa phải staffing-gap view. Dự án chưa có scheduled headcount hoặc actual available agents, vì vậy không được gọi chênh lệch planned-vs-actualized requirement là understaffing.

## 4. Chạy load và validation

```powershell
python src/bootstrap_database.py
python src/load_analytics_marts.py
python src/validate_analytics_warehouse.py
```

DDL và SQL KPI:

```text
sql/01_analytics_schema.sql
sql/02_powerbi_views.sql
sql/03_powerbi_kpi_queries.sql
```

Bằng chứng đối soát:

```text
reports/data_quality/postgres_warehouse_reconciliation.json
reports/data_quality/postgres_warehouse_reconciliation.md
reports/data_quality/postgres_warehouse_reconciliation.sha256
```

## 5. Kết nối Power BI

1. Chọn **Get data → PostgreSQL database**.
2. Server: `localhost:5432`.
3. Database: `call_center_wfm`.
4. Chọn **Import** cho MVP.
5. Đăng nhập bằng PostgreSQL credentials trong `.env`; không đưa password vào PBIX, tài liệu hoặc Git.
6. Trong Navigator, chọn schema `analytics`.

Mô hình khuyến nghị:

- Trang Executive: `vw_kpi_daily_queue`, `vw_powerbi_queue_interval`.
- Trang Forecast & Staffing: `vw_powerbi_forecast_interval`, `vw_kpi_forecast_weekly_model`, `vw_powerbi_model_evaluation`, `vw_powerbi_staffing_interval`.
- Service-type drill-down: `vw_kpi_service_type_daily`.
- Refresh card/tooltip: `vw_powerbi_refresh_status`, lọc `load_id` lớn nhất.

Nếu import fact tables thay vì flattened views, tạo quan hệ dimension-to-fact `1:*`, single direction. Không tạo quan hệ trực tiếp fact-to-fact. Dùng `target_date_key` và `target_interval_key` cho forecast/staffing facts; dùng `date_key` và `interval_key` cho observed facts.

## 6. Phần chưa thể làm trung thực

Các SQL cho consecutive understaffed intervals, attendance, late login, adherence, occupancy và agent/team ranking chưa được triển khai vì chưa có schedule/attendance/state/agent-team marts. Chỉ bổ sung sau khi workforce synthetic data được tạo, gắn nhãn và kiểm tra độc lập với actual call outcome.
