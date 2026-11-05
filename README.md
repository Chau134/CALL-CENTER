# Call Center Workforce Management & Analytics

Dự án portfolio mô phỏng quy trình Workforce Management (WFM) cho một Call Center: từ dữ liệu cuộc gọi, dự báo volume, tính nhu cầu nhân sự, theo dõi staffing gap đến dashboard vận hành.

> Trạng thái hiện tại: dữ liệu Technion đủ 12 tháng đã được audit, ETL và đối soát; foundation marts đủ 17.520 interval đã hoàn thành. Sáu rolling backtest folds, ba models, AHT proxy forecast và workload-based staffing requirement đã chạy thật. Chưa tạo schedule/attendance/state synthetic, chưa load warehouse marts vào PostgreSQL và chưa làm Power BI.

## Mục tiêu MVP

- Chuẩn hóa dữ liệu cuộc gọi theo interval 30 phút.
- Dự báo `agent_demand_calls` theo interval và đánh giá bằng rolling-origin backtesting; `offered_calls` vẫn được giữ để báo cáo inbound traffic.
- Tính productive agents và scheduled agents cần thiết, có xét occupancy và shrinkage.
- So sánh required, scheduled và actual available headcount.
- Phân tích KPI vận hành và hiệu suất agent/team.
- Xây dựng 3 trang Power BI có drill-through và bộ lọc nhất quán.

## Tài liệu bắt đầu

Đọc [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) để xem:

- phạm vi MVP và phần nâng cao;
- data model và data dictionary tối thiểu;
- công thức KPI/WFM;
- hướng dẫn thực hiện từng bước;
- kế hoạch 4 tuần và phương án rút gọn 7 ngày;
- checklist kiểm thử và tiêu chí hoàn thành.

Các quyết định đã khóa nằm trong:

- [config/project.yml](config/project.yml): tham số nghiệp vụ và forecasting;
- [docs/metric_definitions.md](docs/metric_definitions.md): định nghĩa KPI và quy tắc biên;
- [docs/data_sources.md](docs/data_sources.md): đánh giá và khuyến nghị nguồn dữ liệu cho Bước 2.
- [docs/source_data_dictionary.md](docs/source_data_dictionary.md): giải thích 17 trường nguồn và cách xem dữ liệu an toàn.
- [docs/etl_rules.md](docs/etl_rules.md): quy tắc sửa lỗi, phân luồng, trường dẫn xuất và interval mart.
- [docs/missing_fields_plan.md](docs/missing_fields_plan.md): data dictionary và thứ tự bổ sung các trường còn thiếu.
- [docs/forecast_staffing_methodology.md](docs/forecast_staffing_methodology.md): target, backtest, model selection, AHT proxy và staffing assumptions.

## Chạy và kiểm tra ETL

```powershell
python src/transform_calls.py
python src/validate_transformed_data.py
```

Kết quả đối soát gần nhất nằm tại `reports/data_quality/etl_reconciliation.md`. Dữ liệu ETL nằm trong `data/interim/technion/`; raw source không bị chỉnh sửa.

## Chạy foundation marts, forecast và staffing

```powershell
python src/build_foundation_marts.py
python src/validate_foundation_marts.py
python src/run_forecast_staffing.py
python src/validate_forecast_staffing.py
```

Marts nằm tại `data/processed/technion/`. Báo cáo model gần nhất nằm tại `reports/model_evaluation/forecast_evaluation.md`.

## Kiến trúc dự kiến

`Raw/Synthetic data -> Python ETL & Forecasting -> PostgreSQL -> Power BI -> Insights`

## Chạy môi trường phát triển

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
jupyter lab
```

Môi trường hiện dùng Python 3.12.0 và PostgreSQL 18.6 tại `localhost:5432`. Thông tin đăng nhập cục bộ được đọc từ `.env`, không được commit vào repository.

Khởi tạo database và các schema sau khi đã cấu hình `.env`:

```powershell
python src/bootstrap_database.py
python src/check_database.py
```

## Nguyên tắc minh bạch

Nếu dùng dữ liệu tự tạo, mọi bảng, biểu đồ và README phải ghi rõ **synthetic data**. Chỉ đưa vào CV các chức năng đã chạy được và có bằng chứng trong repository.
