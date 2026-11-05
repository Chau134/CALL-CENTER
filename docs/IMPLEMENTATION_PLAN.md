# Blueprint triển khai Call Center WFM & Analytics

## 1. Kết quả cuối cùng cần đạt

Sản phẩm hoàn chỉnh không chỉ là một dashboard. Nó phải chứng minh được một chuỗi phân tích có thể kiểm tra:

1. Dữ liệu nguồn được kiểm tra và chuẩn hóa.
2. Volume được tổng hợp đúng theo interval 30 phút.
3. Forecast được đánh giá trên dữ liệu chưa dùng để huấn luyện.
4. Forecast được chuyển thành nhu cầu nhân sự bằng giả định WFM rõ ràng.
5. Staffing gap và KPI agent được tính thống nhất giữa Python, SQL và Power BI.
6. Dashboard trả lời được câu hỏi vận hành và dẫn đến hành động cụ thể.

Đối tượng sử dụng giả định:

- WFM Analyst: forecast, staffing requirement, staffing gap.
- Operations Manager: service level, abandon rate, AHT, tình trạng thiếu/thừa người.
- Team Leader: attendance, adherence và hiệu suất agent.

## 2. Các câu hỏi nghiệp vụ

Dashboard phải trả lời tối thiểu các câu hỏi sau:

- Volume cao nhất vào ngày và interval nào?
- Forecast sai nhiều nhất ở đâu và sai theo hướng over-forecast hay under-forecast?
- Interval nào thiếu người, thiếu bao nhiêu và ảnh hưởng KPI dịch vụ ra sao?
- Team/agent nào có AHT, attendance hoặc adherence bất thường?
- Chênh lệch giữa scheduled HC và available HC đến từ absence, late login hay hoạt động ngoài production?
- Nếu volume, AHT hoặc shrinkage thay đổi, nhu cầu nhân sự thay đổi thế nào?

## 3. Phạm vi được khóa

### 3.1 MVP bắt buộc

- Một queue/kênh inbound voice, một múi giờ duy nhất.
- Interval 30 phút.
- Tối thiểu 12 tuần dữ liệu; tốt hơn là 6-12 tháng.
- Forecast volume offered; so sánh ít nhất seasonal naive và Holt-Winters.
- Rolling-origin backtesting, không chia train/test ngẫu nhiên.
- Staffing theo capacity, occupancy và shrinkage.
- KPI queue, team và agent.
- PostgreSQL làm tầng dữ liệu phục vụ Power BI.
- Ba trang Power BI: Executive Overview, Forecast & Staffing, Agent Performance.

### 3.2 Phần nâng cao sau MVP

- Erlang C với mục tiêu Service Level, ví dụ 80% cuộc gọi được trả lời trong 20 giây.
- SARIMA/Prophet hoặc mô hình có holiday/event regressors.
- Nhiều queue/skill và multi-skill routing.
- Intraday reforecasting.
- What-if parameters cho volume uplift, AHT, shrinkage và occupancy.
- Phân tích schedule adherence từ agent state events.

### 3.3 Ngoài phạm vi ban đầu

- Tối ưu lịch ca tự động bằng linear/integer programming.
- Speech analytics, sentiment, QA nội dung cuộc gọi.
- Realtime streaming.
- Mô hình dự đoán nghỉ việc của nhân viên.

Việc khóa phạm vi giúp dự án có chiều sâu và hoàn thành được. Chỉ mở rộng sau khi toàn bộ MVP đã vượt qua checklist kiểm thử.

## 4. Định nghĩa nghiệp vụ và công thức

### 4.1 Volume và service

- `Offered Calls = Answered Calls + Abandoned Calls`.
- `Answer Rate = Answered Calls / Offered Calls`.
- `Abandon Rate = Abandoned Calls / Offered Calls`.
- `AHT = (Talk Seconds + Hold Seconds + ACW Seconds) / Handled Calls`.
- `ASA = Total Answer Wait Seconds / Answered Calls`.
- `Service Level = Calls Answered Within Threshold / Eligible Offered Calls`.

Cần ghi rõ quy tắc với short abandons. Ví dụ: cuộc gọi bỏ máy trong 5 giây có được loại khỏi mẫu số Service Level hay không. Chọn một quy tắc, ghi vào data dictionary và dùng nhất quán.

### 4.2 Forecast accuracy

- `Error = Actual - Forecast`; số dương nghĩa là under-forecast.
- `MAE = mean(abs(Error))`.
- `RMSE = sqrt(mean(Error^2))`.
- `WAPE = sum(abs(Error)) / sum(Actual)`.
- `Bias = sum(Forecast - Actual) / sum(Actual)`.

MAPE không ổn khi actual bằng 0 hoặc rất nhỏ. Với dữ liệu interval, dùng WAPE làm KPI chính; vẫn có thể báo MAE/RMSE/MAPE để so sánh với yêu cầu ban đầu.

### 4.3 Staffing theo interval cho MVP

Với interval 30 phút:

```text
workload_hours = forecast_volume * forecast_aht_seconds / 3600
productive_agents = ceil(workload_hours / (interval_hours * occupancy_target))
scheduled_agents = ceil(productive_agents / (1 - shrinkage_rate))
staffing_gap = available_agents - productive_agents
schedule_gap = scheduled_headcount - scheduled_agents
```

Giá trị khởi đầu có thể dùng để demo, không phải chuẩn cố định:

- `interval_hours = 0.5`
- `occupancy_target = 0.85`
- `shrinkage_rate = 0.30`

Ví dụ: 45 calls, AHT 360 giây trong 30 phút tạo 4.5 workload hours. Với occupancy 85%, cần `ceil(4.5 / (0.5 × 0.85)) = 11` productive agents; nếu shrinkage 30%, cần schedule `ceil(11 / 0.7) = 16` agents.

Lưu ý: công thức `daily workload / shift hours` chỉ dùng cho ước tính FTE tổng theo ngày. Không dùng nó để kết luận đủ người trong từng interval.

### 4.4 Erlang C ở giai đoạn nâng cao

Input gồm arrival rate, AHT, interval length, target answer time và target service level. Tìm số agent nhỏ nhất thỏa cả:

- Service Level mục tiêu;
- maximum occupancy, ví dụ 85%;
- sau đó gross-up theo shrinkage để ra số người cần schedule.

Phải kiểm thử hàm Erlang C bằng các ví dụ cố định và đảm bảo không tính shrinkage hai lần.

### 4.5 Agent và attendance

- `Attendance Rate = Attended Scheduled Days / Scheduled Work Days`.
- `Absence Rate = Absent Scheduled Hours / Scheduled Hours`.
- `Late Minutes = max(0, Actual Login - Scheduled Start - Grace Period)`.
- `Early Logout Minutes = max(0, Scheduled End - Actual Logout - Grace Period)`.
- `Occupancy = Handling Time / Logged-in Available Time`.
- `Utilization = Productive Time / Paid Time`.
- `Schedule Adherence = Time In Adherent State / Scheduled Production Time`.
- `FCR = Resolved On First Contact / Eligible Resolved Contacts`.
- `CSAT = Positive Survey Responses / Valid Survey Responses`.

Không thay thế adherence bằng `login hours / scheduled hours`; đó chỉ là một proxy và phải được gắn nhãn rõ nếu chưa có state-level data.

## 5. Data model đề xuất

### 5.1 Grain của từng bảng

| Bảng | Grain | Khóa chính gợi ý | Mục đích |
|---|---|---|---|
| `dim_date` | một ngày | `date_key` | calendar, week, month, holiday |
| `dim_time_interval` | một interval 30 phút | `interval_key` | giờ bắt đầu/kết thúc, daypart |
| `dim_agent` | một phiên bản agent | `agent_key` | team, leader, hire date, status |
| `dim_team` | một team | `team_key` | team và team leader |
| `dim_queue` | một queue/skill | `queue_key` | queue phân tích |
| `fact_call` | một cuộc gọi/contact | `call_id` | trạng thái, timestamps, durations |
| `fact_queue_interval` | ngày × interval × queue | composite key | offered, answered, abandoned, AHT, SL |
| `fact_forecast_interval` | run date × target interval × model | composite key | forecast, actual, errors |
| `fact_schedule` | agent × ca làm việc | `schedule_id` | scheduled start/end/break |
| `fact_attendance` | agent × ngày/phiên login | `attendance_id` | actual login/logout, absence |
| `fact_agent_state` | agent × state event | `state_event_id` | adherence nâng cao |
| `fact_agent_daily_kpi` | agent × ngày × queue | composite key | handled calls, AHT, FCR, CSAT |
| `fact_staffing_interval` | ngày × interval × queue | composite key | required/scheduled/available/gap |

Không nối trực tiếp nhiều fact table với nhau trong Power BI. Các fact dùng chung dimension Date, Interval, Agent, Team và Queue.

### 5.2 Cột tối thiểu của dữ liệu nguồn

`calls.csv`:

```text
call_id, queue_id, agent_id, offered_at, answered_at, ended_at,
call_status, talk_seconds, hold_seconds, acw_seconds,
wait_seconds, resolved_first_contact, csat_score
```

`agents.csv`:

```text
agent_id, agent_name, team_id, team_leader, hire_date, employment_status
```

`schedules.csv`:

```text
schedule_id, agent_id, work_date, scheduled_start, scheduled_end,
scheduled_break_minutes, shift_name
```

`attendance.csv`:

```text
attendance_id, agent_id, work_date, actual_login, actual_logout,
absence_type, overtime_minutes
```

Nếu không có dữ liệu thật, bộ sinh synthetic phải tạo được seasonality theo weekday/intraday, random noise, holidays/events, absence, late login và quan hệ hợp lý giữa understaffing với abandon/service level.

## 6. Kiến trúc và cấu trúc repository

```text
CALL-CENTER/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── config/
│   └── project.yml
├── data/
│   ├── raw/
│   ├── synthetic/
│   ├── interim/
│   └── processed/
├── docs/
│   ├── IMPLEMENTATION_PLAN.md
│   ├── data_dictionary.md
│   └── metric_definitions.md
├── notebooks/
│   ├── 01_data_audit.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_forecast_experiments.ipynb
│   └── 04_staffing_validation.ipynb
├── src/
│   ├── generate_synthetic_data.py
│   ├── validate_data.py
│   ├── transform.py
│   ├── forecast.py
│   ├── staffing.py
│   └── load_postgres.py
├── sql/
│   ├── 01_schema.sql
│   ├── 02_load_staging.sql
│   ├── 03_marts.sql
│   ├── 04_kpi_views.sql
│   └── 05_data_quality_checks.sql
├── tests/
│   ├── test_metrics.py
│   ├── test_forecast.py
│   └── test_staffing.py
├── powerbi/
│   ├── call_center_wfm.pbix
│   └── dax_measures.md
├── reports/
│   ├── model_evaluation.md
│   └── business_insights.md
└── screenshots/
```

Giữ notebook cho khám phá; logic chạy lặp lại phải chuyển sang `src/` và có test.

## 7. Hướng dẫn thực hiện từng bước

Trạng thái thực thi ngày 2026-11-04:

| Bước | Trạng thái | Bằng chứng |
|---|---|---|
| 0 — giả định nghiệp vụ | Hoàn thành | `config/project.yml`, `docs/metric_definitions.md` |
| 1 — môi trường | Hoàn thành | `.venv`, `requirements.txt`, 6 tests pass, `pip check` pass |
| 2 — nguồn dữ liệu | Hoàn thành | Technion Anonymous Bank; raw archive + documentation + SHA-256 đã xác nhận |
| 11a — nền tảng PostgreSQL | Hoàn thành sớm | PostgreSQL 18.6; database `call_center_wfm`; schema `raw`, `staging`, `analytics` |

### Bước 0 — Chốt giả định nghiệp vụ

Tạo `config/project.yml` chứa timezone, interval size, service-level threshold, short-abandon threshold, occupancy target, shrinkage, forecast horizon và ngày đặc biệt. Không hard-code các giá trị này ở nhiều file.

Đầu ra: một trang metric definitions đã được khóa.

### Bước 1 — Khởi tạo môi trường

Trong PowerShell tại thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install pandas numpy scipy statsmodels scikit-learn sqlalchemy psycopg[binary] pyyaml matplotlib seaborn jupyter pytest
pip freeze > requirements-lock.txt
```

Tạo `.env.example`, không commit `.env`, password hay dữ liệu nhạy cảm.

Đầu ra: môi trường chạy được và `pytest` khởi động không lỗi.

### Bước 2 — Thu thập hoặc tạo dữ liệu

Ưu tiên nguồn theo thứ tự:

1. Dữ liệu đã ẩn danh từ hệ thống được phép sử dụng.
2. Public dataset có license rõ ràng.
3. Synthetic data tự tạo và gắn nhãn rõ ràng.

Nếu tạo synthetic, sinh ít nhất 180 ngày, 100-200 agents và interval 30 phút. Dùng random seed cố định. Không tạo volume hoàn toàn ngẫu nhiên; thêm intraday curve, weekday factor, trend, holiday/event uplift và noise.

Đầu ra: file raw không bị chỉnh sửa thủ công và một tài liệu provenance.

### Bước 3 — Data audit trước khi làm sạch

**Trạng thái: hoàn thành cho bộ Technion Anonymous Bank.** Baseline trước ETL nằm tại `reports/data_quality/raw_baseline.json` và `.md`.

Kiểm tra:

- schema, data type và timezone;
- missing theo cột;
- duplicate `call_id`;
- timestamp theo thứ tự `offered <= answered <= ended`;
- duration âm hoặc vượt ngưỡng hợp lý;
- orphan agent/team/queue key;
- status không nằm trong danh mục;
- coverage theo ngày và interval;
- volume/AHT outlier.

Xuất `reports/data_quality_report.csv`; không chỉ hiển thị kết quả trong notebook.

### Bước 4 — Làm sạch và tạo interval mart

**Trạng thái: hoàn thành.** Đã tạo đủ 17.520 wall-clock interval, queue mart, service-type mart, calendar/time/queue dimensions, coverage và DST flags. Đối soát nằm tại `reports/data_quality/foundation_marts_reconciliation.json` và `.md`.

- Parse timestamp và chuẩn hóa timezone.
- Tạo `date_key`, `interval_start`, `interval_key`.
- Chuẩn hóa answered/abandoned/transferred.
- Tính handle time từ talk + hold + ACW.
- Tổng hợp `fact_queue_interval`.
- Reindex đầy đủ mọi interval; interval không có call phải có volume bằng 0, không bị mất khỏi chuỗi thời gian.

Đối chiếu bắt buộc:

```text
raw distinct call_id = cleaned answered + abandoned + excluded documented records
daily sum(interval offered) = daily offered
```

### Bước 5 — EDA có mục tiêu

Tạo biểu đồ và insight cho:

- daily trend và rolling average;
- heatmap weekday × interval;
- distribution của AHT và wait time;
- answer/abandon rate theo staffing gap;
- missing intervals và event anomalies;
- team/agent distribution để phát hiện denominator quá nhỏ.

Mỗi biểu đồ phải có một câu kết luận nghiệp vụ, không chỉ mô tả hình dạng.

### Bước 6 — Thiết kế backtesting

**Trạng thái: hoàn thành.** Pipeline dùng 6 rolling folds, mỗi fold 7 ngày; không random split.

Ví dụ với 180 ngày:

- Train ban đầu: 12 tuần.
- Horizon: 7 ngày hoặc 336 interval.
- Step: 7 ngày.
- Tạo 4-8 rolling folds.
- Chỉ fit trên dữ liệu có trước thời điểm dự báo.

Tính metric tổng và theo weekday/interval. Không dùng random train-test split vì gây leakage thời gian.

### Bước 7 — Xây baseline trước

**Trạng thái: hoàn thành.** Đã chạy seasonal naive 7 ngày và trung bình cùng weekday/interval của 4 tuần.

Tối thiểu gồm:

- Last value.
- Seasonal naive: cùng interval của 7 ngày trước.
- Trung bình cùng weekday + interval của 4 tuần gần nhất.

Baseline tốt nhất là mốc để mô hình nâng cao phải vượt qua. Nếu Holt-Winters không vượt baseline ổn định, giữ baseline và giải thích trung thực.

### Bước 8 — Huấn luyện và chọn forecast model

**Trạng thái: hoàn thành phiên bản MVP.** Đã so sánh seasonal naive, trung bình cùng weekday/interval 4 tuần, Holt–Winters và XGBoost trên cùng 6 rolling folds. Baseline trung bình 4 tuần được chọn với aggregate WAPE 0,1795; XGBoost đứng thứ hai với WAPE 0,1861, Holt–Winters không vượt baseline.

XGBoost dùng calendar features và weekly lags 336/672/1.008/1.344 interval; không dùng lag ngắn có thể đọc actual trong test horizon. SARIMA là stretch goal. Lưu cho mỗi forecast:

```text
forecast_run_at, target_interval, queue_id, model_name,
forecast_volume, lower_bound, upper_bound, actual_volume,
training_start, training_end
```

Chọn model dựa trên WAPE + bias + độ ổn định qua folds, không chỉ dựa vào một holdout đẹp.

### Bước 9 — Forecast AHT

**Trạng thái: hoàn thành với AHT proxy.** Dùng weighted same-weekday/interval history và fallback trailing 28 ngày, không dùng actual AHT tương lai.

MVP có thể dùng median AHT của cùng weekday/interval trong 4 tuần gần nhất, có floor/ceiling hợp lý. Không dùng actual AHT tương lai để tính required staffing vì đó là leakage.

So sánh hai kịch bản:

- `planned staffing`: forecast volume × forecast AHT;
- `actualized staffing analysis`: actual volume × actual AHT, chỉ dùng hậu kiểm.

### Bước 10 — Tính staffing requirement

**Trạng thái: hoàn thành workload-based baseline.** Đã tạo 336 interval requirement cho fold cuối; chưa phải Erlang C và chưa có scheduled/available staffing thực tế.

Implement hàm thuần trong `src/staffing.py`, nhận volume, AHT, interval, occupancy và shrinkage. Viết unit test cho:

- volume bằng 0;
- shrinkage bằng 0;
- giá trị mẫu 45 calls/360 giây;
- không chia cho 0;
- rounding luôn hướng lên;
- input âm phải bị từ chối.

Xuất `fact_staffing_interval` gồm forecast workload, productive requirement, scheduled requirement, scheduled HC, available HC và các gap.

### Bước 11 — Xây PostgreSQL

**Trạng thái: hoàn thành cho 9 marts hiện có.** Đã tạo dimensions/facts với PK, FK, check constraints và indexes; transactional full-snapshot loader đã load 131.544 rows và đối soát khớp source. Chín Power BI/KPI views và load audit đã được tạo trong schema `analytics`.

Thực hiện theo thứ tự:

1. Tạo schema `raw`, `staging`, `analytics`.
2. Load raw/staging bằng Python.
3. Tạo dimensions và fact tables với primary/foreign keys.
4. Tạo views KPI phục vụ Power BI.
5. Thêm index cho date, interval, agent, queue.
6. Chạy SQL data-quality checks sau mỗi lần load.

ETL phải idempotent: chạy lại cùng input không tạo duplicate.

### Bước 12 — Viết SQL phân tích

**Trạng thái: hoàn thành phần dữ liệu hiện có.** Đã có executive KPI, peak interval dùng window function, forecast accuracy theo tuần/model, rolling 7/28-day volume/AHT proxy và planned staffing requirement. Các query understaffing, attendance, agent/team ranking chờ workforce marts; không mô phỏng KPI khi chưa có denominator hợp lệ.

Các query portfolio bắt buộc:

- peak intervals bằng window functions;
- forecast accuracy theo tuần và model;
- consecutive understaffed intervals;
- team ranking nhưng kèm minimum sample size;
- scheduled vs actual login và late minutes;
- rolling 7/28-day AHT và volume;
- agent outlier so với median của team, không chỉ toàn công ty.

### Bước 13 — Thiết kế Power BI model

**Trạng thái: hoàn thành.** PBIP hiện có 10 warehouse objects, star-schema với 13 relationships, `_Measures` gồm 40 DAX measures, technical columns đã ẩn và theme đã áp dụng. Toàn bộ 40 measures đã thực thi thành công bằng DAX smoke test; PostgreSQL grain/uniqueness checks pass.

- Import các analytics views, ưu tiên star schema.
- Tạo một Date table và mark as date table.
- Quan hệ dimension-to-fact là 1:* và single direction nếu không có lý do đặc biệt.
- Ẩn technical keys.
- Measures nằm trong một measure table; không dùng calculated columns cho phép tính động có thể làm bằng measure.
- Tạo `Last Refresh Time` và tooltip giải thích metric.

### Bước 14 — Xây ba trang dashboard

**Trạng thái: baseline dashboard đã dựng trong PBIP.** Ba trang MVP gồm Executive Overview (9 visuals), Forecast & Staffing (10 visuals), Service Mix & Data Quality (10 visuals). Power BI đã nạp, render và lưu thành công cả 29 visuals; Agent Performance tiếp tục chờ workforce marts. Việc còn lại là conditional formatting cho heatmaps, chuẩn hóa slicer dropdown, bổ sung navigation/reset filters/tooltips và hoàn thành visual QA trước khi publish.

**Trang 1 — Executive Overview**

- KPI cards: Offered, Answer Rate, Abandon Rate, AHT, Service Level.
- Line chart: Actual vs Forecast.
- Column/area chart: Required vs Available HC.
- Heatmap: staffing gap theo weekday × interval.
- Insight box: ba vấn đề đáng chú ý và hành động đề xuất.

**Trang 2 — Forecast & Staffing**

- WAPE, Bias, MAE theo model/horizon.
- Forecast confidence band.
- Volume, AHT, workload và requirement theo interval.
- Under/overstaffing hours.
- What-if parameters ở giai đoạn nâng cao.

**Trang 3 — Agent Performance**

- Attendance, adherence/proxy, handled calls, AHT, FCR, CSAT.
- Team comparison và trend.
- Scatter AHT vs CSAT/FCR để tránh ranking một chiều.
- Drill-through agent detail.
- Cảnh báo sample size nhỏ.

Không tạo một composite score bí ẩn. Nếu cần score, công bố normalization, trọng số và minimum sample size.

### Bước 15 — Reconciliation và kiểm thử

Chọn ba lát cắt cố định: một ngày, một team và một agent. Đối chiếu cùng KPI ở bốn tầng:

```text
raw file -> Python processed output -> PostgreSQL view -> Power BI visual
```

Sai số tiền/tỷ lệ do rounding phải có tolerance ghi rõ. Tổng calls phải khớp tuyệt đối sau khi trừ các record bị loại có lý do.

### Bước 16 — Viết insight và recommendation

Mỗi insight dùng cấu trúc:

```text
Observation -> Evidence -> Operational impact -> Recommended action -> Limitation
```

Ví dụ: “Thứ Hai 09:00-11:00 under-forecast trung bình X%, trùng với Y interval understaffed và abandon rate cao hơn Z điểm %. Đề xuất đưa break ra khỏi khung giờ này hoặc tăng buffer forecast; cần kiểm chứng thêm vì dữ liệu là synthetic.”

### Bước 17 — Hoàn thiện portfolio

README cuối cần có:

- business problem và persona;
- kiến trúc;
- nguồn dữ liệu và giới hạn;
- data model;
- metric definitions;
- phương pháp forecast/backtest;
- kết quả thật sau khi chạy;
- ảnh dashboard;
- ba insight và khuyến nghị;
- cách tái tạo môi trường;
- phần “what I would improve next”.

## 8. Kế hoạch thực tế trong 4 tuần

| Tuần | Công việc | Deliverable/điểm kiểm soát |
|---|---|---|
| 1 | khóa scope, data dictionary, lấy/tạo dữ liệu, audit, ETL interval | raw provenance, DQ report, interval mart đã reconcile |
| 2 | EDA, baseline, rolling backtest, model selection, AHT forecast | model evaluation report, forecast table, không leakage |
| 3 | staffing logic, unit tests, PostgreSQL schema/views, KPI SQL | staffing mart, test pass, SQL reconciliation |
| 4 | Power BI, cross-layer QA, insights, README, screenshots | PBIX, dashboard QA, portfolio hoàn chỉnh |

Nhịp làm việc gợi ý: 2-3 giờ/ngày, 5 ngày/tuần. Mỗi tuần chỉ được coi là xong khi deliverable vượt qua checkpoint, không phải khi đã “dành đủ thời gian”.

## 9. Phương án rút gọn 7 ngày

| Ngày | Phạm vi bắt buộc |
|---|---|
| 1 | chốt metric + tạo/thu thập data + data dictionary |
| 2 | audit, clean, interval mart và reconciliation |
| 3 | EDA + seasonal naive + Holt-Winters + backtest |
| 4 | forecast AHT + staffing capacity + unit tests |
| 5 | PostgreSQL schema/views + SQL KPI checks |
| 6 | ba trang Power BI + đối chiếu lát cắt mẫu |
| 7 | insight, README, screenshots và chạy lại toàn pipeline |

Trong bản 7 ngày, bỏ SARIMA, Erlang C, multi-queue và state-level adherence.

## 10. Definition of Done

### Data

- [ ] Nguồn và license/provenance được ghi rõ.
- [ ] Timezone và interval được khóa.
- [ ] Duplicate, missing, orphan key và timestamp invalid có báo cáo.
- [ ] Tổng raw-to-mart được reconcile.
- [ ] Synthetic data được gắn nhãn ở README và dashboard.

### Forecast

- [ ] Có ít nhất hai baseline và một candidate model.
- [ ] Dùng rolling time-series backtest.
- [ ] Báo WAPE, bias, MAE/RMSE và metric theo segment.
- [ ] Không dùng actual tương lai trong feature/AHT plan.
- [ ] Forecast được lưu kèm run date và model version.

### Staffing

- [ ] Requirement tính theo interval, rounding up.
- [ ] Occupancy và shrinkage tách biệt.
- [ ] Planned và actualized staffing không bị trộn.
- [ ] Unit tests qua các edge cases.
- [ ] Required, scheduled và available HC có định nghĩa riêng.

### BI và SQL

- [ ] Star schema, không fact-to-fact tùy tiện.
- [ ] KPI nhất quán giữa Python, SQL và DAX.
- [ ] Slicer Date/Team/Agent/Queue hoạt động đúng.
- [ ] Có drill-through và tooltip định nghĩa metric.
- [ ] Ba lát cắt kiểm thử khớp qua bốn tầng.

### Portfolio

- [ ] Có ảnh dashboard rõ ràng.
- [ ] Có ba insight định lượng và hành động đề xuất.
- [ ] Có limitations và next steps.
- [ ] Không có secret, PII hay file dữ liệu không được phép công bố.
- [ ] CV chỉ mô tả những chức năng đã thật sự hoàn thành.

## 11. Rủi ro thường gặp và cách tránh

| Rủi ro | Hậu quả | Cách xử lý |
|---|---|---|
| random train/test split | metric forecast quá đẹp | rolling-origin backtest |
| MAPE với actual bằng 0 | metric vô nghĩa | dùng WAPE làm chính |
| lấy actual AHT tương lai | leakage | forecast AHT riêng |
| nhầm occupancy với utilization | staffing sai | khóa metric definitions |
| shrinkage tính hai lần | overstaffing | gross-up một lần sau productive requirement |
| mất interval volume 0 | chuỗi thời gian méo | reindex complete grid |
| ranking agent ít cuộc gọi | kết luận thiếu công bằng | minimum sample size + confidence flag |
| fact-to-fact relationships | Power BI double count | shared dimensions/star schema |
| dashboard nhiều màu/KPI | khó ra quyết định | ba trang, mỗi trang một persona |
| synthetic trông như dữ liệu thật | thiếu minh bạch | watermark và disclosure |

## 12. Thứ tự mở rộng sau MVP

1. Erlang C và validation bằng test cases.
2. Holiday/event features và prediction intervals.
3. Intraday reforecast theo actual-to-date.
4. Agent state data để tính adherence thật.
5. Shift optimization với constraints về luật lao động, break và skill.

Chỉ chuyển sang bước tiếp theo khi baseline, staffing mart và cross-layer reconciliation của MVP đã ổn định.
