# Kế hoạch xây dựng dashboard Power BI

## 1. Mục tiêu

Xây dựng Power BI dashboard cho dự án Call Center WFM, sử dụng PostgreSQL `call_center_wfm`, schema `analytics`, nhằm trả lời ba nhóm câu hỏi:

1. Call center đang tiếp nhận bao nhiêu cuộc gọi và chất lượng phục vụ ra sao?
2. Mô hình dự báo nào tốt nhất, forecast sai ở đâu và nhu cầu nhân sự theo interval là bao nhiêu?
3. Service mix, coverage và chất lượng dữ liệu có vấn đề gì cần lưu ý?

Dashboard MVP gồm ba trang:

1. **Executive Overview**
2. **Forecast & Staffing**
3. **Service Mix & Data Quality**

Trang Agent Performance chưa thực hiện vì chưa có schedule, attendance, agent-state và team mapping hợp lệ. Không tạo agent/adherence/occupancy KPI khi chưa có denominator cần thiết.

## 2. Nguồn dữ liệu

Kết nối Power BI:

```text
Connector: PostgreSQL database
Server: localhost:5432
Database: call_center_wfm
Schema/object prefix: analytics.
Mode: Import
```

Power BI Navigator hiển thị object theo dạng `schema.object_name`, ví dụ:

```text
analytics.dim_date
analytics.fact_queue_interval_complete
analytics.vw_powerbi_refresh_status
```

Không chọn các schema hệ thống như `pg_catalog` hoặc `information_schema`.

## 3. Tables cần import

### 3.1 Dimensions

- `analytics.dim_date`
- `analytics.dim_time_interval`
- `analytics.dim_queue`
- `analytics.dim_service_type`

### 3.2 Facts

- `analytics.fact_queue_interval_complete`
- `analytics.fact_service_type_interval`
- `analytics.fact_forecast_interval`
- `analytics.fact_model_evaluation`
- `analytics.fact_staffing_requirement`

### 3.3 Refresh metadata

- `analytics.vw_powerbi_refresh_status`

Không import đồng thời toàn bộ fact tables và các flattened `vw_powerbi_*` views khác ở phiên bản đầu, vì có thể tạo hai đường tính KPI và dẫn tới double count. Các KPI views trong PostgreSQL được dùng để kiểm tra kết quả Power BI hoặc làm phương án dashboard đơn giản hóa.

## 4. Data model

### 4.1 Relationships

Tất cả relationship dimension-to-fact dùng:

```text
Cardinality: One-to-many (1:*)
Cross-filter direction: Single
```

Quan hệ Date:

```text
dim_date[date_key]
  -> fact_queue_interval_complete[date_key]
  -> fact_service_type_interval[date_key]
  -> fact_forecast_interval[target_date_key]
  -> fact_staffing_requirement[target_date_key]
```

Quan hệ Time Interval:

```text
dim_time_interval[interval_key]
  -> fact_queue_interval_complete[interval_key]
  -> fact_service_type_interval[interval_key]
  -> fact_forecast_interval[target_interval_key]
  -> fact_staffing_requirement[target_interval_key]
```

Quan hệ Queue:

```text
dim_queue[queue_id]
  -> fact_queue_interval_complete[queue_id]
  -> fact_service_type_interval[queue_id]
  -> fact_forecast_interval[queue_id]
  -> fact_staffing_requirement[queue_id]
```

Quan hệ Service Type:

```text
dim_service_type[service_type_code]
  -> fact_service_type_interval[service_type_code]
```

`fact_model_evaluation` và `vw_powerbi_refresh_status` để disconnected trong MVP. Không tạo relationship fact-to-fact.

### 4.1.1 Kiểm tra grain và uniqueness trước khi nối

- Đã xác minh bằng PostgreSQL constraints và warehouse validator: `dim_date[date_key]`, `dim_time_interval[interval_key]`, `dim_queue[queue_id]`, `dim_service_type[service_type_code]` là primary key, không null và duy nhất.
- Grain thực tế đã khóa: queue fact = `date × interval × queue`; service fact = `date × interval × service type × queue`; forecast fact = `forecast run × target date × target interval × queue`; staffing fact = `selected forecast run × target date × target interval × queue`; evaluation fact = `model × version × scope × fold`.
- Foreign keys đã được PostgreSQL enforcement và validator xác nhận không orphan. Không nối facts trực tiếp.
- Date/interval dimensions lọc theo **target date/time** đối với forecast và staffing. Nếu phân tích theo forecast origin, bổ sung role-playing dimension hoặc inactive relationship + `USERELATIONSHIP`, không thay thế ngầm target date.
- Forecast hiện có 6 fold liên tiếp, không chồng target window. Với selected model có 2.016 rows và 2.016 target keys duy nhất. Staffing hiện có 336 rows, một queue, một selected run và 336 target keys duy nhất. Nếu sau này thêm scenario/snapshot hoặc fold chồng lấn, phải bổ sung filter scope trước khi SUM/MAX.

### 4.1.2 Model slicers và filter scope

- Vì `fact_model_evaluation` disconnected, slicer Model trên forecast fact **không** tự lọc evaluation. MVP: dùng slicer riêng cho model evaluation và filter visual-level; phương án mở rộng: `dim_model` với khóa duy nhất, quan hệ 1:* đến hai facts sau khi xác nhận tên cột và tính duy nhất.
- `dim_service_type` chỉ lọc `fact_service_type_interval`. Không sử dụng slicer Service Type như bộ lọc toàn báo cáo nếu các facts khác không có khóa tương ứng.
- Slicer Backtest Fold và Evaluation Scope chỉ điều khiển những visual có grain tương ứng; dùng Edit interactions để tránh gây hiểu nhầm. Các KPI “All Folds / overall” là mốc cố định, không phản ánh fold slicer.


### 4.2 Cấu hình dimensions

- Mark `dim_date[calendar_date]` là Date Table.
- Sort `dim_date[day_name]` bằng `day_of_week_iso`.
- Sort `dim_date[month_name]` bằng `month_number`.
- Sort `dim_time_interval[start_time]` bằng `interval_number`.
- Sort `dim_time_interval[daypart]` bằng một sort column nếu sau này cần thứ tự `overnight → morning → afternoon → evening`.

### 4.3 Ẩn technical columns

Ẩn khỏi Report view:

- `date_key`, `interval_key`, `target_date_key`, `target_interval_key`;
- `etl_run_id`;
- `generation_method`, `generation_version`;
- `source_reference`, `source_fact`;
- các timestamp kỹ thuật không dùng trực tiếp trên visual.

Không xóa cột khỏi model nếu cột vẫn cần cho relationship hoặc QA.

## 5. Measure table và DAX

Tạo một table riêng tên `_Measures` để chứa tất cả measures. Không dùng implicit measures cho KPI quan trọng.

### 5.1 Queue measures

```DAX
Offered Calls =
SUM(fact_queue_interval_complete[offered_calls])

Agent Demand Calls =
SUM(fact_queue_interval_complete[agent_demand_calls])

Answered Calls =
SUM(fact_queue_interval_complete[answered_calls])

Abandoned Calls =
SUM(fact_queue_interval_complete[abandoned_calls])

Queue Abandoned Calls =
SUM(fact_queue_interval_complete[queue_abandoned_calls])

VRU Abandoned Calls =
SUM(fact_queue_interval_complete[vru_abandoned_calls])

Short Abandoned Calls =
SUM(fact_queue_interval_complete[short_abandon_calls])

Answer Rate =
DIVIDE([Answered Calls], [Offered Calls])

Abandon Rate =
DIVIDE([Abandoned Calls], [Offered Calls])

Short Abandon Rate =
DIVIDE([Short Abandoned Calls], [Offered Calls])

Service Level =
DIVIDE(
    SUM(fact_queue_interval_complete[answered_within_20s]),
    SUM(fact_queue_interval_complete[service_level_denominator])
)

AHT Proxy Seconds =
DIVIDE(
    SUM(fact_queue_interval_complete[total_service_seconds_for_aht]),
    SUM(fact_queue_interval_complete[aht_eligible_calls])
)

Average Wait Seconds All Calls =
DIVIDE(
    SUM(fact_queue_interval_complete[total_wait_seconds]),
    [Offered Calls]
)
```

Không dùng `AVERAGE(service_level_rate)` hoặc `AVERAGE(aht_proxy_seconds)` để tổng hợp nhiều interval. Luôn tính lại từ tổng tử số và mẫu số.

### 5.2 Forecast measures

Actual được lặp lại cho mỗi model trong forecast fact. Vì vậy các measure Actual dùng cho biểu đồ tổng phải lọc một model hoặc selected model để tránh nhân actual volume theo số model. Với dữ liệu hiện tại, `is_selected_model = TRUE()` tạo đúng một observation/prediction pair cho từng target vì sáu fold không chồng lấn. Phải kiểm tra lại điều kiện này nếu pipeline bổ sung snapshot hoặc rolling folds chồng nhau.

Quy ước đã đối chiếu với PostgreSQL: cột interval `error_actual_minus_forecast = Actual - Forecast`, còn Bias được tính `sum(Forecast - Actual) / sum(Actual)`. Vì vậy Bias âm = under-forecast, Bias dương = over-forecast.

```DAX
Selected Forecast Calls =
CALCULATE(
    SUM(fact_forecast_interval[forecast_agent_demand_calls]),
    fact_forecast_interval[is_selected_model] = TRUE()
)

Selected Forecast Actual =
CALCULATE(
    SUM(fact_forecast_interval[actual_agent_demand_calls]),
    fact_forecast_interval[is_selected_model] = TRUE()
)

Selected Forecast Absolute Error =
CALCULATE(
    SUM(fact_forecast_interval[absolute_error]),
    fact_forecast_interval[is_selected_model] = TRUE()
)

Selected Forecast WAPE =
DIVIDE(
    [Selected Forecast Absolute Error],
    [Selected Forecast Actual]
)

Selected Forecast Bias =
DIVIDE(
    [Selected Forecast Calls] - [Selected Forecast Actual],
    [Selected Forecast Actual]
)

Selected Forecast MAE =
CALCULATE(
    AVERAGE(fact_forecast_interval[absolute_error]),
    fact_forecast_interval[is_selected_model] = TRUE()
)

Selected Forecast RMSE =
VAR MeanSquaredError =
    CALCULATE(
        AVERAGE(fact_forecast_interval[squared_error]),
        fact_forecast_interval[is_selected_model] = TRUE()
    )
RETURN
    SQRT(MeanSquaredError)
```

**Lưu ý:** Các measure `Selected Forecast ...` hợp lệ với grain hiện tại đã được QA. `AVERAGE(absolute_error)` và `SQRT(AVERAGE(squared_error))` phản ánh MAE/RMSE trên toàn bộ interval rows được chọn; không được trung bình MAE, RMSE hoặc WAPE của nhiều fold để suy ra toàn kỳ. Nếu model slicer cho phép chọn model khác, measure `is_selected_model = TRUE()` vẫn cố định vào model production; trang so sánh model dùng evaluation fact và slicer riêng.

Model evaluation cards/bar chart dùng aggregate rows:

```DAX
Model WAPE (All Folds) =
CALCULATE(
    MAX(fact_model_evaluation[wape]),
    fact_model_evaluation[backtest_fold] = "ALL",
    fact_model_evaluation[evaluation_scope] = "overall"
)

Model Bias (All Folds) =
CALCULATE(
    MAX(fact_model_evaluation[bias]),
    fact_model_evaluation[backtest_fold] = "ALL",
    fact_model_evaluation[evaluation_scope] = "overall"
)

Model MAE (All Folds) =
CALCULATE(
    MAX(fact_model_evaluation[mae]),
    fact_model_evaluation[backtest_fold] = "ALL",
    fact_model_evaluation[evaluation_scope] = "overall"
)

Model RMSE (All Folds) =
CALCULATE(
    MAX(fact_model_evaluation[rmse]),
    fact_model_evaluation[backtest_fold] = "ALL",
    fact_model_evaluation[evaluation_scope] = "overall"
)
```

PostgreSQL primary key và readiness QA đã xác nhận có đúng một aggregate row cho mỗi `model × version × scope × fold`; hiện có bốn rows tại `backtest_fold=ALL`, `evaluation_scope=overall`. `MAX` ở đây chỉ lấy scalar từ row duy nhất, không phải phương pháp tổng hợp nhiều evaluation rows.

### 5.3 Staffing measures

```DAX
Planned Workload Hours =
SUM(fact_staffing_requirement[workload_hours])

Actualized Workload Hours =
SUM(fact_staffing_requirement[actualized_workload_hours])

Peak Productive Agents =
MAX(fact_staffing_requirement[required_productive_agents])

Peak Scheduled Agents =
MAX(fact_staffing_requirement[required_scheduled_agents])

Required Productive Agent Hours =
SUMX(
    fact_staffing_requirement,
    fact_staffing_requirement[required_productive_agents]
        * fact_staffing_requirement[interval_minutes] / 60
)

Required Scheduled Agent Hours =
SUMX(
    fact_staffing_requirement,
    fact_staffing_requirement[required_scheduled_agents]
        * fact_staffing_requirement[interval_minutes] / 60
)

Intervals Requiring Staff =
CALCULATE(
    COUNTROWS(fact_staffing_requirement),
    fact_staffing_requirement[required_scheduled_agents] > 0
)
```

**Cảnh báo về peak:** Với MVP hiện chỉ có một queue và một selected run, `MAX(required_*_agents)` trả đúng peak 15/22. Nếu có nhiều queue và cần peak toàn trung tâm, phải SUM theo target date × interval trước rồi mới MAX qua interval; đồng thời loại duplicate scenario/snapshot.

`Intervals Requiring Staff = COUNTROWS(...)` trả đúng 205/336 với MVP vì mỗi row là một target interval duy nhất. Nếu có nhiều queue/scenario, phải đếm distinct target date × target interval sau khi xác định scope.

Các agent-hours được SUM qua interval nhưng có thể trùng nếu nhiều snapshot/scenario. `Actualized Workload Hours` là retrospective, không phải số nhân sự thực tế đi làm.

Không tạo `Staffing Gap`, `Understaffed Intervals` hoặc `Available Agents` cho đến khi có schedule/attendance/state marts.

### 5.4 Service-type measures

Schema và reconciliation đã xác nhận service-type fact cộng khớp queue fact cho Offered, Agent Demand, Answered và Abandoned Calls. Tạo các measure riêng, không dùng queue measures trên visual service type:

```DAX
Service Offered Calls =
SUM(fact_service_type_interval[offered_calls])

Service Answered Calls =
SUM(fact_service_type_interval[answered_calls])

Service Abandoned Calls =
SUM(fact_service_type_interval[abandoned_calls])

Service Answer Rate =
DIVIDE([Service Answered Calls], [Service Offered Calls])

Service Abandon Rate =
DIVIDE([Service Abandoned Calls], [Service Offered Calls])

Service AHT Proxy Seconds =
DIVIDE(
    SUM(fact_service_type_interval[service_seconds_sum_for_aht]),
    SUM(fact_service_type_interval[valid_for_aht_calls])
)
```

### 5.5 Refresh measure

```DAX
Last Warehouse Load =
MAX(vw_powerbi_refresh_status[loaded_at_utc])
```

## 6. Trang 1 — Executive Overview

### 6.1 Mục tiêu

Trả lời nhanh:

- Tổng inbound traffic là bao nhiêu?
- Bao nhiêu call được answer/abandon?
- Service Level và AHT proxy đang ở mức nào?
- Ngày/khung giờ nào tạo áp lực lớn nhất?

### 6.2 Slicers

- Date range: `dim_date[calendar_date]`
- Queue: `dim_queue[queue_name]`
- Day of week: `dim_date[day_name]`
- Daypart: `dim_time_interval[daypart]`
- Holiday: `dim_date[is_holiday]`

### 6.3 Visuals

1. KPI cards:
   - Offered Calls
   - Answer Rate
   - Abandon Rate
   - Service Level
   - AHT Proxy Seconds
2. Daily traffic line chart:
   - Axis: `calendar_date`
   - Values: Offered, Answered, Abandoned
3. Offered vs Service Level combo chart:
   - Column: Offered Calls
   - Line: Service Level
4. Intraday heatmap:
   - Rows: `day_name`
   - Columns: `start_time`
   - Values: Agent Demand Calls
5. Service Level heatmap hoặc conditional-format matrix.
6. Holiday vs normal-day comparison.

### 6.4 Tooltip

- Offered Calls
- Agent Demand Calls
- Answer Rate
- Abandon Rate
- Service Level denominator
- AHT eligible calls

Tooltip phải ghi rõ AHT hiện là `AHT proxy`, chưa có hold/ACW.

## 7. Trang 2 — Forecast & Staffing

### 7.1 Mục tiêu

Trả lời:

- Model nào được chọn và vì sao?
- Forecast sai bao nhiêu, sai theo hướng over/under forecast?
- Sai số thay đổi theo model, fold và forecast horizon như thế nào?
- Planned workload và staffing requirement theo interval là bao nhiêu?

### 7.2 Slicers

- Model name
- Backtest fold
- Evaluation scope
- Target date/week
- Operating interval

Slicer model cho biểu đồ Actual vs Forecast nên mặc định chọn `same_weekday_interval_mean_4w`. Có thể dùng visual-level filter `is_selected_model = TRUE` thay vì cho người dùng bỏ chọn model.

### 7.3 Visuals

1. Model cards:
   - Selected model
   - WAPE
   - Bias
   - MAE
   - RMSE
2. Model comparison bar chart:
   - Axis: model name
   - Value: WAPE
   - Filter: fold `ALL`, scope `overall`
3. Actual vs Forecast line chart:
   - Axis: target local interval
   - Values: actual và forecast
   - Filter: selected model
4. Error by forecast horizon:
   - Axis: `forecast_horizon_intervals`
   - Value: average absolute error
5. Productive vs scheduled requirement line chart.
6. Planned vs retrospective actualized workload chart.
7. Staffing requirement heatmap:
   - Rows: day name
   - Columns: interval start
   - Values: required scheduled agents

### 7.4 Cảnh báo trình bày

- Theo quy ước DAX `Forecast - Actual`: Bias âm nghĩa là under-forecast; bias dương nghĩa là over-forecast. Đối chiếu định nghĩa cột `fact_model_evaluation[bias]` trước khi dùng chung nhãn.
- Actualized staffing fields chỉ dùng hậu kiểm.
- Workload-based requirement chưa phải Erlang C.
- Không gọi planned-vs-actualized requirement là staffing gap.

## 8. Trang 3 — Service Mix & Data Quality

### 8.1 Mục tiêu

Thay thế tạm thời trang Agent Performance bằng phân tích service type và bằng chứng chất lượng dữ liệu.

### 8.2 Visuals

1. Offered Calls theo service type.
2. Service-type share bằng 100% stacked bar.
3. Answer/Abandon Rate theo service type.
4. AHT proxy theo service type.
5. Service type × interval heatmap.
6. Coverage status breakdown.
7. Zero-filled interval count theo reason.
8. Last Warehouse Load card.
9. Data-origin label/tooltip để phân biệt observed, derived và synthetic trong tương lai.

Không dùng pie/donut nếu số nhóm lớn hoặc nhãn khó đọc.

## 9. Thiết kế giao diện

### 9.1 Theme màu

| Ý nghĩa | Màu |
|---|---|
| Actual/Observed | `#1F4E78` |
| Forecast | `#F28E2B` |
| Positive/Answered | `#2A9D8F` |
| Abandoned/Error | `#D9534F` |
| Neutral | `#6B7280` |
| Background | `#F7F9FC` |

### 9.2 Quy tắc trình bày

- Không quá 6–8 visuals trên một trang.
- Dùng cùng một vị trí slicer trên ba trang.
- Percentage hiển thị 1–2 chữ số thập phân.
- Calls hiển thị whole number và thousand separator.
- AHT hiển thị giây hoặc `mm:ss`, nhưng phải nhất quán.
- Dùng màu đỏ cho adverse outcome; không dùng màu chỉ để trang trí.
- Thêm page navigation và nút Reset Filters.
- Thêm tooltip giải thích metric dễ hiểu sai.
- Tiêu đề visual phải trả lời câu hỏi nghiệp vụ, không chỉ ghi tên cột.

## 10. Đối soát bắt buộc

### 10.1 Mốc toàn kỳ

Các KPI Power BI phải khớp PostgreSQL reconciliation:

| KPI | Giá trị kỳ vọng |
|---|---:|
| Offered Calls | 440.844 |
| Agent Demand Calls | 417.149 |
| Answered Calls | 353.143 |
| Abandoned Calls | 87.701 |
| Answer Rate | 80,1061% |
| Abandon Rate | 19,8939% |
| Service Level | 46,4631% |
| AHT proxy | 194,2519 giây |

### 10.2 Forecast

| Model | WAPE kỳ vọng |
|---|---:|
| `same_weekday_interval_mean_4w` | 17,9539% |
| `xgboost_lag_calendar` | 18,6071% |
| `seasonal_naive_7d` | 22,9716% |
| `holt_winters_additive_damped` | 27,8119% |

Selected model phải là `same_weekday_interval_mean_4w`.

### 10.3 Staffing fold cuối

- Planned workload: khoảng 531,07 giờ.
- Peak productive requirement: 15 agents.
- Peak scheduled requirement: 22 agents.
- Interval có scheduled requirement lớn hơn 0: 205/336.

### 10.4 Cross-layer QA

Đối chiếu tối thiểu ba lát cắt:

1. Toàn bộ năm 1999.
2. Một ngày cụ thể có traffic.
3. Tuần forecast cuối, 25/12/1999–31/12/1999.

Cho mỗi lát cắt, so sánh:

```text
processed CSV -> PostgreSQL fact/view -> Power BI measure/visual
```

Không publish dashboard nếu totals không khớp hoặc actual forecast volume bị nhân lên do hiển thị nhiều models/folds/snapshots cùng lúc.

### 10.5 SQL/Power BI QA bổ sung

- Kiểm tra `COUNT(*)`, `COUNT(DISTINCT business_key)` và `COUNT(*) FILTER (WHERE key IS NULL)` theo grain đã xác nhận; kiểm tra orphan dimension keys.
- Kiểm tra `is_selected_model` có đúng một model theo phạm vi sử dụng; kiểm tra các target forecast có bị lặp qua fold/origin/run.
- Kiểm tra reconciliation theo đúng filter: ngày, queue, operating interval, coverage status; so sánh **weighted ratios**, không average tỷ lệ.
- Kiểm tra các dòng `backtest_fold=ALL`, `evaluation_scope=overall` là duy nhất theo model và cùng tập dữ liệu.
- Đối chiếu staffing peak theo interval toàn trung tâm (nếu applicable), agent-hours và distinct interval counts.
- Kiểm tra refresh metadata có thực sự cung cấp `loaded_at_utc` và các row-count/reconciliation fields trước khi tạo card; nếu không có, dùng SQL QA/view riêng, không tự tạo số.
- Test slicer propagation và các visual disconnected; ghi lại filter nào không tác động đến visual nào.
- Test Import refresh sau khi warehouse thay đổi, timezone UTC/local, null vs zero, ngày đóng cửa và interval zero-filled.


## 11. Thứ tự triển khai

### Giai đoạn 1 — Data model

- Import tables.
- Kiểm tra data types.
- Tạo relationships.
- Mark Date Table và cấu hình sort.
- Ẩn technical fields.

### Giai đoạn 2 — Measures và QA nền

- Tạo `_Measures`.
- Viết queue measures.
- Đối chiếu KPI toàn kỳ.
- Viết forecast/staffing measures.
- Kiểm tra selected-model filter và duplicated actual risk.

### Giai đoạn 3 — Dashboard pages

- Xây Executive Overview.
- Xây Forecast & Staffing.
- Xây Service Mix & Data Quality.
- Thêm tooltips, navigation và reset filters.

### Giai đoạn 4 — Cross-layer validation

- Đối chiếu ba lát cắt cố định.
- Kiểm tra slicer propagation.
- Kiểm tra visual interactions.
- Kiểm tra blank/zero behavior.
- Kiểm tra labels phân biệt observed/derived/actualized.

### Giai đoạn 5 — Portfolio handoff

- Lưu PBIX ngoài Git nếu dung lượng lớn.
- Chụp screenshot ba trang vào thư mục tài liệu dự án.
- Cập nhật README với trạng thái dashboard thực tế.
- Ghi lại insight và hành động đề xuất có số liệu hỗ trợ.

## 12. Definition of Done

- [ ] Star schema đúng, không có fact-to-fact relationship.
- [ ] Relationships là `1:*`, single direction.
- [ ] Date table được đánh dấu và sort đúng.
- [ ] Queue KPI tính từ additive numerators/denominators.
- [ ] Actual forecast không bị nhân theo số model.
- [ ] Model comparison dùng fold `ALL`, scope `overall`.
- [ ] Staffing planned và actualized được gắn nhãn riêng.
- [ ] Không hiển thị staffing gap/adherence/occupancy giả.
- [x] Ba trang có slicer, tooltip và navigation nhất quán.
- [ ] KPI toàn kỳ khớp PostgreSQL reconciliation.
- [ ] Ba lát cắt QA khớp giữa CSV, SQL và Power BI.
- [ ] README chỉ mô tả các chức năng dashboard đã hoàn thành thật.
- [ ] Đã xác minh grain, uniqueness, null keys và orphan keys cho mọi quan hệ.
- [ ] Forecast đã loại trùng theo model/fold/origin/snapshot và thống nhất quy ước Bias.
- [ ] Model slicer và evaluation cards được cấu hình rõ phạm vi lọc.
- [ ] Peak staffing và số interval được tính đúng khi có nhiều queue/scenario.
- [ ] Service Type slicer không bị hiểu nhầm là lọc tất cả facts.
- [ ] Refresh Import, timezone, zero/blank và reconciliation metadata được kiểm tra.

## 13. Trạng thái xác minh và triển khai

Schema, tên cột, primary/foreign keys, grain, row counts, model selection và các mốc tại mục 10 đã được xác minh trực tiếp trên PostgreSQL bằng `src/validate_analytics_warehouse.py`. Readiness QA riêng cho Power BI phải được chạy lại sau mỗi thay đổi warehouse.

Đã hoàn thành trong repository và Power BI Desktop:

- PostgreSQL analytics schema và 9 marts;
- KPI/serving views và reconciliation report;
- Power BI theme JSON;
- DAX measure library;
- SQL và Python readiness checks;
- semantic model với 10 warehouse objects, 13 relationships và 40 measures;
- ba dashboard pages với 41 visuals;
- 11 slicer phân loại dạng Dropdown và 3 slicer ngày dạng Between;
- ba heatmap dùng conditional-formatting gradient;
- ba nút điều hướng và một nút Reset Filters trên mỗi trang;
- tooltip giải thích giới hạn của AHT Proxy trên các visual liên quan;
- visual-level render QA và screenshots cho cả ba trang;
- PBIR validation đạt `0 error`, `0 warning`.

Còn lại cho vòng nghiệm thu nghiệp vụ: chạy lại các lát cắt đối soát CSV/SQL/Power BI sau lần refresh dữ liệu tiếp theo và ghi nhận insight cuối cùng cho portfolio.
