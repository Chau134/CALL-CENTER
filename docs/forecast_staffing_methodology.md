# Forecast và staffing methodology

## 1. Target được sử dụng

Dữ liệu Technion ghi nhận toàn bộ call đi vào VRU. Vì không phải mọi VRU call đều tạo workload cho agent, pipeline tách hai metric:

```text
offered_calls = toàn bộ clean calls đi vào VRU
agent_demand_calls = answered_calls + queue_abandoned_calls
```

Kết quả toàn năm:

- `offered_calls`: 440.844;
- `agent_demand_calls`: 417.149;
- `vru_abandoned_calls`: 23.695.

`offered_calls` được giữ để báo cáo inbound traffic. `agent_demand_calls` là target cho forecast và staffing.

## 2. Time-series dataset

- Grain: một queue × interval 30 phút.
- Khoảng thời gian: 01/01/1999–31/12/1999.
- Số wall-clock interval: 17.520.
- Queue MVP: `INBOUND_SUPPORT`.
- Timezone assumption: `Asia/Jerusalem`.
- Interval không có call được điền 0 vì tài liệu nguồn xác nhận archive chứa toàn bộ calls trong 12 tháng và VRU hoạt động 24/7; đồng thời đủ 12 file, checksum và row reconciliation đều hợp lệ.
- DST ambiguous/nonexistent local times có flag; UTC fields để null khi nguồn không đủ thông tin chọn fold.

Operating hours trong tài liệu nguồn là gần đúng. Dữ liệu có 2.072 agent-demand calls nằm ngoài khung staffed-hours cấu hình, vì vậy pipeline không tự ép forecast ngoài giờ bằng 0.

## 3. Rolling-origin backtest

Không dùng random train/test split.

| Tham số | Giá trị |
|---|---:|
| Horizon | 7 ngày = 336 interval |
| Số fold | 6 |
| Bước dịch fold | 7 ngày |
| Seasonal period | 336 interval |
| Model selection metric | WAPE |
| Tie-break | absolute bias, sau đó MAE |

Mỗi forecast record lưu:

- simulated forecast origin;
- artifact generation time UTC;
- training end;
- target interval;
- horizon interval number;
- model/version;
- forecast và actual;
- error, absolute error và squared error.

Metric được tính ở ba scope: `overall`, `operating` và `closed`.

## 4. Models

### Seasonal naive 7 ngày

```text
forecast(t) = actual(t - 336 intervals)
```

### Trung bình cùng weekday/interval trong 4 tuần

```text
forecast(t) = mean(
  actual(t - 336),
  actual(t - 672),
  actual(t - 1008),
  actual(t - 1344)
)
```

### Holt–Winters

- Additive trend;
- damped trend;
- additive weekly seasonality;
- seasonal period 336;
- negative predictions được clip về 0.

### XGBoost lag + calendar

- Strategy: direct multi-step cho toàn bộ horizon 7 ngày;
- calendar features: interval trong ngày, weekday, tháng, ngày trong năm, holiday/DST và operating-hours flags đã biết tại forecast origin;
- target lags: 336, 672, 1.008 và 1.344 interval, tương ứng cùng thời điểm của 1–4 tuần trước;
- statistics từ bốn weekly lags: mean, standard deviation, min và max;
- objective: `reg:squarederror`; 300 trees, depth 4, learning rate 0,05, `tree_method=hist` và seed 42;
- negative predictions được clip về 0.

Không dùng lag 30 phút hoặc 1 ngày. Với horizon 336 interval, những lag này sẽ đọc actual nằm trong chính test window ở các bước dự báo sau. Lag nhỏ nhất của XGBoost bằng đúng horizon, nên mọi target feature của từng fold đều nằm trước forecast origin.

## 5. Kết quả model selection

Aggregate trên sáu rolling folds, scope `overall`:

| Model | WAPE | Bias | MAE | RMSE |
|---|---:|---:|---:|---:|
| `same_weekday_interval_mean_4w` | 0,1795 | -0,0121 | 4,7801 | 8,0246 |
| `xgboost_lag_calendar` | 0,1861 | 0,0108 | 4,9540 | 8,0561 |
| `seasonal_naive_7d` | 0,2297 | -0,0045 | 6,1161 | 10,2972 |
| `holt_winters_additive_damped` | 0,2781 | -0,2079 | 7,4048 | 11,9786 |

Model được chọn là `same_weekday_interval_mean_4w`. XGBoost đứng thứ hai nhưng WAPE cao hơn baseline khoảng 0,65 điểm phần trăm, nên chưa được dùng để tạo staffing forecast. Kết quả này cũng cho thấy không nên chọn mô hình chỉ vì phức tạp hơn.

Ở operating intervals, model được chọn có WAPE 0,1772 và bias -0,0119. WAPE ở closed intervals cao do mẫu số actual rất nhỏ; phải đọc cùng actual volume, không dùng riêng tỷ lệ này để kết luận chất lượng tổng thể.

## 6. Forecast AHT proxy

Nguồn không có hold và ACW, do đó dùng `aht_proxy_seconds`, không gọi là full AHT.

Cho mỗi target interval:

1. Lấy tối đa bốn interval cùng weekday/time trong lịch sử train.
2. Tính weighted AHT bằng `total_service_seconds_for_aht / aht_eligible_calls`.
3. Nếu không có eligible call ở các lag tương ứng, dùng weighted AHT của 28 ngày train gần nhất.
4. Clip trong percentile 5–95% của interval AHT thuộc tập train.

Không dùng actual AHT của target interval để tính planned staffing.

## 7. Staffing requirement

Staffing hiện dùng workload/capacity baseline, không phải Erlang C:

```text
workload_hours = forecast_agent_demand_calls × forecast_aht_proxy_seconds / 3600

required_productive_agents = CEILING(
    workload_hours / (0.5 × occupancy_target)
)

required_scheduled_agents = CEILING(
    required_productive_agents / (1 - shrinkage_rate)
)
```

Giả định hiện tại:

- occupancy target: 85%;
- shrinkage: 30%;
- interval: 30 phút.

Staffing mart dùng 336 interval của fold cuối và model được chọn. Kết quả planned:

- tổng workload: khoảng 531,07 giờ;
- maximum productive requirement: 15 agents;
- maximum scheduled requirement: 22 agents;
- 205/336 interval có scheduled requirement lớn hơn 0.

Các cột `actualized_*` chỉ dùng hậu kiểm. Chúng không được trình bày như thông tin đã biết tại thời điểm lập kế hoạch.

## 8. Outputs

```text
data/processed/technion/fact_forecast_interval.csv.gz
data/processed/technion/fact_model_evaluation.csv.gz
data/processed/technion/fact_staffing_requirement.csv.gz
reports/model_evaluation/forecast_evaluation.json
reports/model_evaluation/forecast_evaluation.md
```

Artifacts hiện có 8.064 forecast rows (4 models × 6 folds × 336 interval), 84 evaluation rows và 336 staffing rows.

Chạy lại và kiểm tra:

```powershell
python src/run_forecast_staffing.py
python src/validate_forecast_staffing.py
```

## 9. Giới hạn

- AHT hiện là service-time proxy, chưa có hold/ACW.
- Operating hours là mô tả gần đúng từ tài liệu nguồn.
- Holiday fields là calendar reference, không chứng minh call center đóng cửa.
- Staffing method chưa mô hình hóa probability of wait hoặc Service Level như Erlang C.
- Chưa có schedule/attendance/state thật nên chưa tính được staffing gap, adherence hoặc occupancy quan sát.
