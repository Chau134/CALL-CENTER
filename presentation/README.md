# Call Center WFM project presentation

## Output

- `CALL_CENTER_WFM_Project_Report.pptx`: báo cáo PowerPoint 16:9, 14 slide, tiếng Việt.
- `CALL_CENTER_WFM_Project_Report.pdf`: bản PDF được PowerPoint render từ PPTX.
- `build_call_center_presentation.py`: script tái tạo deck từ số liệu và screenshots trong repository.
- `preview/`: ảnh PNG từng slide dùng để kiểm tra trực quan.

## Nội dung

1. Trang bìa.
2. Tóm tắt điều hành và KPI chính.
3. Bài toán nghiệp vụ và người dùng.
4. Nguồn dữ liệu, phạm vi và provenance.
5. Kiến trúc giải pháp end-to-end.
6. ETL và data-quality evidence.
7. Dimensional model và lớp KPI.
8. Executive Overview dashboard.
9. So sánh bốn forecast models, gồm XGBoost.
10. Forecast & Staffing dashboard và staffing logic.
11. Service Mix & Data Quality dashboard.
12. Chất lượng kỹ thuật và khả năng tái lập.
13. Giới hạn và cách diễn giải có trách nhiệm.
14. Next steps.

## Tái tạo

```powershell
python presentation\build_call_center_presentation.py
```

Deck sử dụng trực tiếp screenshots tại `reports/powerbi_interactions/`. Nếu thay dashboard, chụp lại ảnh rồi chạy script để cập nhật PPTX.

## Nguồn số liệu chính

- `reports/data_quality/raw_baseline.md`
- `reports/data_quality/foundation_marts_reconciliation.md`
- `reports/data_quality/powerbi_semantic_model_qa.md`
- `docs/forecast_staffing_methodology.md`
- `docs/data_provenance.md`
- `docs/metric_definitions.md`
