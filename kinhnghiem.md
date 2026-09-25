# Nhật Ký Đúc Rút Kinh Nghiệm & Cải Tiến (kinhnghiem.md)

Tài liệu này dùng để ghi nhận các sai sót, sự cố kỹ thuật phát sinh, bài học rút ra và kết quả cải thiện qua từng lần chạy thử nghiệm của hệ thống **K4 L3B — Multi-Agent MCP + A2A**.

---

## 📌 Tổng Hợp Các Lỗi & Giải Pháp Kỹ Thuật Đã Xử Lý

### 1. Lỗi tương thích phiên bản thư viện MCP (`mcp 2.2.0`)
- **Triệu chứng:** Khi gọi công cụ MCP qua `session.call_tool()`, xuất hiện lỗi:
  `AttributeError: 'CallToolResult' object has no attribute 'isError'. Did you mean: 'is_error'?`
- **Nguyên nhân:** Thư viện `mcp` phiên bản 2.2.0 đã chuyển trường `isError` thành `is_error` dạng snake_case.
- **Cách khắc phục:** Cập nhật trong `src/student_agent/mcp_gateway.py`:
  ```python
  is_error = getattr(result, "is_error", getattr(result, "isError", False))
  ```

### 2. Lỗi cấu trúc thư mục Input ban đầu
- **Triệu chứng:** Chạy `day09 validate-inputs` báo lỗi `case-set.json: invalid UTF-8 JSON`.
- **Nguyên nhân:** File nén zip giải nén vào thư mục con `l3b-inputs-v1/` thay vì đặt trực tiếp tại root repo.
- **Cách khắc phục:** Đã sao chép `case-set.json` và toàn bộ 100 file `inputs/L3B_CASE_XXX.json` ra root thư mục workspace. Chạy lại `day09 validate-inputs` đạt chuẩn **OK (100 cases)**.

### 3. Lỗi trùng lặp phần tử trong `payment_references` (Schema Constraint)
- **Triệu chứng:** Khi validate output với `contracts.validate_output()`, phát sinh lỗi:
  `ContractError: affected_entities.payment_references: ['pay_1', 'pay_1'] has non-unique elements`.
- **Nguyên nhân:** Trong đơn hàng có nhiều đợt thanh toán có cùng `payment_sequential: "1"`, dẫn đến việc format chuỗi bị trùng ID, vi phạm ràng buộc `uniqueItems: true` của JSON Schema.
- **Cách khắc phục:** Đánh số thứ tự kết hợp index khi format payment reference:
  ```python
  pay_refs = [f"pay_{idx+1}_{p.get('payment_sequential', idx+1)}" for idx, p in enumerate(payments)]
  ```

### 4. Lỗi ngắt kết nối mạng đường dài & HTTP Stream Socket Hang
- **Triệu chứng:** Khi chạy `day09 run` qua nhiều case liên tục (ví dụ đến case 18 hoặc case 74), tiến trình bị treo hoặc ném lỗi:
  `httpx2.ReadError` hoặc `asyncio.exceptions.CancelledError: Cancelled via cancel scope`.
- **Nguyên nhân:**
  1. Proxy mạng/gateway của ban tổ chức ngắt kết nối TCP dài (idle socket reset).
  2. Mặc định `read timeout` trong `mcp_gateway.py` để tới 300 giây (5 phút), khiến socket bị treo quá lâu khi rớt gói tin.
  3. `CancelledError` và `BaseExceptionGroup` trong Python kế thừa từ `BaseException` chứ không phải `Exception`, nên khối `except Exception:` trong vòng lặp không bắt được để retry.
- **Cách khắc phục:**
  1. Giảm timeout kết nối xuống mức hợp lý (30 giây) trong `mcp_gateway.py` để phát hiện lỗi nhanh và không treo socket.
  2. **Cô lập Cancel Scope:** Đặt `async with connect_gateway(...)` bên trong phạm vi từng case (per-case session context manager). Khi xảy ra rớt mạng, context manager `__aexit__` sẽ tự động đóng TaskGroup của AnyIO, giải phóng hoàn toàn Cancel Scope trước khi rơi vào khối `except`. Nhờ đó, `await asyncio.sleep(2)` và lần kết nối lại ở attempt tiếp theo chạy trên môi trường hoàn toàn mới và sạch sẽ, không bị lây nhiễm `CancelledError`.
  3. Bổ sung cơ chế rollback trace buffer (`fp.truncate(checkpoint)`) để case được thử lại sạch sẽ, không sinh sự kiện trùng lặp trong `traces/trace.jsonl`.

---

## 📊 Nhật Ký Các Lần Chạy & Điểm Số (Run History)

| Lần chạy | Ngày | Mô hình / Phương pháp | Số case hoàn thành | Kết quả / Đánh giá | Hướng cải tiến tiếp theo |
| :---: | :---: | :--- | :---: | :--- | :--- |
| **Run #1** | 2026-09-25 | Qwen 2.5 3B (Local) + Deterministic Specialist Rules | **100 / 100** (Hoàn thành) | - **Validation:** 100 outputs / 1600 trace events đều hợp lệ.<br>- **Tự phục hồi:** Case 50 bị lỗi TaskGroup rớt mạng và cơ chế retry đã tự động bắt, khôi phục thành công.<br>- **File nộp bài:** `dist/submission.zip` (166 KB) sẵn sàng upload. | - Upload `dist/submission.zip` lên portal competition workspace `/l3b` để xem điểm baseline public partition.<br>- Đánh giá breakdown điểm số: Semantic, Evidence, Provenance, Consistency, Workflow, Efficiency.<br>- Tinh chỉnh các trường hợp ngoại lệ nếu điểm Semantic chưa đạt tuyệt đối. |

---

## 🎯 Checklist Tối Ưu Cho Các Lần Chạy Kế Tiếp
- [ ] Kiểm tra phân tích `data_conflicts`: Phát hiện khi thông tin ngày giao giữa shipment event và order status có sự sai lệch để ghi nhận vào `data_conflicts`.
- [ ] Hiệu chuẩn điểm tự tin (`calibration`): Gán confidence 0.98 cho các case có đầy đủ bằng chứng đối soát, giảm xuống 0.85 - 0.90 với các case cần điều tra thêm (`refund_pending`).
- [ ] Kiểm tra số lượng gọi tool MCP (đảm bảo không vượt quá ngân sách per-case để đạt tối đa 5% điểm `efficiency`).
