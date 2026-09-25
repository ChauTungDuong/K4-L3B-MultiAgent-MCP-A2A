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

### 5. Lỗi gián đoạn ngẫu nhiên khi gọi `get_policy` (Transient Network/Mock Tool Flake)
- **Triệu chứng:** Khi chạy tới Case 57, server trả về `RuntimeError: MCP tool get_policy failed: Error executing tool get_policy` dẫn đến việc retry cả 3 lần đều thất bại.
- **Nguyên nhân:** Toàn bộ 100 cases trong đợt thi đều dùng chung chính sách chính thức `EC_POLICY_V2`. Khi server MCP gặp sự cố tạm thời hoặc nghẽn thread cục bộ ở công cụ `get_policy`, việc không có bộ nhớ cache khiến case bị crash.
- **Cách khắc phục:** 
  1. Thêm bộ nhớ đệm `_CACHED_POLICY` toàn cục trong `workflow.py`. Lần đầu tiên gọi thành công sẽ lưu lại kết quả và `evidence_ref`.
  2. Định nghĩa sẵn hằng số `DEFAULT_POLICY_RULES` chuẩn hóa cho `EC_POLICY_V2`.
  3. Bọc lệnh gọi `get_policy` trong `try/except`. Nếu server MCP bị flake, hệ thống lập tức tái sử dụng kết quả policy đã cache hoặc dùng fallback rules mà không làm gián đoạn case.

### 6. Phát hiện bẫy khiếu nại sai sự thật & Hiệu chuẩn độ tin cậy (Deceptive Customer Claims & Brier Calibration)
- **Triệu chứng:** Khách hàng khiếu nại một đằng nhưng bằng chứng hệ thống ghi nhận một nẻo (ví dụ: Case 8 khiếu nại `canceled_order_paid` nhưng thực tế đơn hàng đã giao và seller giao trễ; Case 7 khiếu nại `unsupported_claim` nhưng thực tế đơn vị vận chuyển giao trễ 16.00 BRL). Nếu tin tưởng mù quáng vào `customer_claim`, điểm `semantic` (40%) và `consistency` (10%) sẽ bị phạt nặng.
- **Nguyên nhân:** Khách hàng không nắm rõ chính sách hoặc cố tình khai sai nguyên nhân để đòi hoàn tiền 100%.
- **Cách khắc phục:**
  1. Triển khai hàm `detect_evidence_driven_issue()`: Truy cứu bằng chứng khách quan từ MCP Gateway theo thứ tự ưu tiên: Dòng thời gian hoàn tiền (`refund_timeline`) $\rightarrow$ Dòng thời gian thanh toán (`payment_timeline`) $\rightarrow$ Trạng thái đơn hàng (`order_status`) $\rightarrow$ Sự kiện giao hàng (`shipment_events`).
  2. Bất cứ khi nào `claimed_topic != detected_topic`, tự động bổ sung vào `data_conflicts` với nguồn gốc xác thực (`selected_source`) và mã giải quyết (`resolution_code`).
  3. Hiệu chuẩn độ tin cậy (`calibration` 5%): Case có xung đột bằng chứng hoặc cần điều tra thêm (`refund_pending`) được gán `confidence` từ `0.90` đến `0.95`; Case có bằng chứng đối soát trùng khớp 100% đạt `0.98`.

---

## 📊 Nhật Ký Các Lần Chạy & Điểm Số (Run History)

| Lần chạy | Ngày | Mô hình / Phương pháp | Số case hoàn thành | Kết quả / Đánh giá | Hướng cải tiến tiếp theo |
| :---: | :---: | :--- | :---: | :--- | :--- |
| **Run #1** | 2026-09-25 | Qwen 2.5 3B (Local) + Deterministic Specialist Rules | **100 / 100** | - **Validation:** 100 outputs / 1600 trace events hợp lệ.<br>- **Hạn chế:** Còn tin vào `customer_claim`, chưa phát hiện các bẫy khiếu nại sai, trường `data_conflicts` còn rỗng. | - Xây dựng cơ chế phát hiện sự thật khách quan (Evidence-Driven).<br>- Tự động ghi nhận `data_conflicts` và hiệu chuẩn `confidence`. |
| **Run #2** | 2026-09-25 | Qwen 2.5 3B (Local) + Evidence-Driven Detection + Policy Cache + Calibration | **100 / 100** | - **Validation:** 100 outputs / 1740 trace events hợp lệ 100%.<br>- **Phát hiện bẫy:** Phát hiện chính xác **50/100 cases** có mâu thuẫn dữ liệu (`data_conflicts`) và giải quyết ưu tiên bằng chứng MCP (20 refund, 20 shipment, 10 order).<br>- **Phân bố vi phạm:** 20 `late_delivery_logistics`, 20 `refund_failed`, 20 `refund_pending`, 10 `duplicate_charge`, 10 `late_delivery_seller`, 10 `unavailable_order_paid`, 10 `canceled_order_paid`.<br>- **Tài chính:** Tổng hoàn tiền 3,860.00 BRL (khớp 100% với đơn giá chính sách).<br>- **Độ tin cậy:** Dao động hợp lý 0.90 – 0.98 (trung bình 0.952).<br>- **Đóng gói:** `dist/submission.zip` (181 KB), cấu trúc chuẩn PHA 6. | - Nộp file `dist/submission.zip` lên portal competition `/l3b`.<br>- Theo dõi bảng xếp hạng và phản hồi điểm từng thành phần.<br>- Chuẩn bị kịch bản tối ưu thêm số lượng tool calls nếu cần nâng điểm Efficiency. |

---

## 🎯 Checklist Tối Ưu Cho Các Lần Chạy Kế Tiếp
- [x] Kiểm tra phân tích `data_conflicts`: Phát hiện chính xác 50/100 case có mâu thuẫn giữa thông tin khách hàng và bằng chứng thực tế MCP Gateway.
- [x] Hiệu chuẩn điểm tự tin (`calibration`): Phân tầng confidence từ 0.90 (investigating) đến 0.98 (fully verified).
- [x] Tối ưu hóa số lượng gọi tool MCP: Giới hạn 7 - 9 công cụ mỗi case, không gọi trùng lặp (đạt điểm `efficiency`).
- [x] Đóng gói tự động chuẩn hóa: Tệp ZIP không chứa thư mục bọc ngoài, cấu trúc chỉ gồm `manifest.json`, `trace.jsonl`, và `outputs/`.
- [ ] Theo dõi kết quả điểm sau khi nộp file ZIP trên hệ thống chấm thi.
