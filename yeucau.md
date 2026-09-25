# K4 L3B — Multi-Agent MCP + A2A: Tài Liệu Yêu Cầu & Hướng Dẫn Kỹ Thuật

Tài liệu này tổng hợp toàn bộ yêu cầu, tiêu chuẩn kỹ thuật, hợp đồng dữ liệu và quy trình thực hiện cho bài toán **K4 L3B — Multi-Agent MCP + A2A** (Điều tra khiếu nại thương mại điện tử đa nguồn).

---

## 1. Mục Tiêu Dự Án

Xây dựng hệ sinh thái **Multi-Agent tự động điều tra và ra quyết định xử lý khiếu nại thương mại điện tử** (tập dữ liệu Olist Brazilian E-commerce).

Hệ thống cần giải quyết trọn vẹn:
1. **Phân giải thực thể (Entity Resolution):** Tìm đúng đơn hàng (`order_id`) mục tiêu từ danh sách ứng viên (`candidate_order_ids`) và gợi ý khách hàng (`customer_unique_id_hint`), xử lý trường hợp khiếu nại sai mã hoặc mập mờ.
2. **Khai thác công cụ MCP (Evidence Gathering):** Thu thập dữ liệu từ MCP Gateway theo nguyên tắc *least privilege*, tránh gọi lặp/thừa để tối ưu điểm hiệu năng (*efficiency*).
3. **Phân tích chuyên môn (Specialist Investigation):**
   - Vận chuyển: trễ do người bán (`seller_delay`) hay đơn vị vận chuyển (`logistics_delay`), thất lạc (`lost`), trả hàng (`returned`).
   - Tài chính: lệch tiền đối soát (`capture_mismatch`), trừ tiền trùng (`duplicate_charge`), tiến trình hoàn tiền (`refund_pending`, `refund_failed`, `refunded`).
   - Xung đột dữ liệu (`data_conflicts`): Phát hiện và xử lý mâu thuẫn giữa các nguồn bằng chứng.
4. **Áp dụng chính sách & Phán quyết (Policy Decision):** Xác định nguyên nhân gốc rễ, đối tượng chịu trách nhiệm, tính toán số tiền bồi hoàn chính xác theo `EC_POLICY_V2` và đề xuất hành động khắc phục.
5. **Ghi vết quy trình Multi-Agent (Observable Trace):** Ghi nhận đầy đủ chu trình tương tác giữa các Agent vào `traces/trace.jsonl` theo chuẩn schema.


---

## 2. Yêu Cầu Về Mô Hình AI (< 10 Tỷ Tham Số)

> [!IMPORTANT]
> **Ràng buộc kích thước mô hình: Dưới 10 tỷ tham số (< 10B parameters).**
> - **Các dòng mô hình hợp lệ:**
>   - `Qwen2.5-7B` / `Qwen2.5-Coder-7B`
>   - `Llama-3.1-8B-Instruct`
>   - `Gemma-2-9B-It`
>   - `Mistral-7B-Instruct-v0.3`
>   - Hoặc các mô hình nhỏ hơn (1B - 3B như `Llama-3.2-3B`, `Qwen2.5-3B`).
> - **Chiến lược tối ưu hóa (Hybrid / Expert System):**
>   - Do môi trường máy trạm có thể có tài nguyên VRAM hạn chế (ví dụ GPU RTX 3050 4GB), hệ thống nên kết hợp:
>     1. **Logic Chuyên gia xác định (Deterministic Expert Logic):** Xử lý toán học, đối soát dòng tiền, tính ngày trễ hạn, map chính sách và phân giải thực thể để đảm bảo **độ chính xác 100% (Consistency & Semantic)** và không bị ảo giác số liệu.
>     2. **Mô hình SLM (< 10B):** Sử dụng để đọc hiểu ngữ cảnh tự nhiên phức tạp của `customer_request.message` nếu cần trích xuất ý định tinh tế mà schema chưa chỉ định rõ.
>   - Hoàn toàn có thể triển khai hệ thống Agent theo kiến trúc Chuyên gia Quy tắc (Deterministic Agentic System) đạt điểm tuyệt đối về tính nhất quán, không phụ thuộc độ trễ hay chi phí của mô hình lớn.

---

## 3. Thiết Lập Môi Trường & Lệnh Vận Hành

### Cấu hình biến môi trường (`.env`)
```dotenv
COMPETITION_API_URL=https://n7-competition.pages.dev
COMPETITION_TEAM_API_KEY=sk-team-...
MCP_ENDPOINT=https://day09-competition.34-142-201-239.sslip.io/mcp
```

### Các lệnh CLI chính (`day09`)
- **Kiểm tra bộ input:**
  ```bash
  day09 validate-inputs
  ```
  *(Kiểm tra `case-set.json` và đủ 100 file trong thư mục `inputs/`)*

- **Kiểm tra kết nối và danh sách tool MCP:**
  ```bash
  day09 mcp-tools
  ```

- **Chạy quy trình điều tra cho toàn bộ 100 case:**
  ```bash
  day09 run
  ```

- **Kiểm tra hợp lệ toàn bộ output và trace:**
  ```bash
  day09 validate
  ```

- **Đóng gói file nộp bài:**
  ```bash
  day09 package --output dist/submission.zip
  ```

---

## 4. Hệ Sinh Thái MCP Gateway (10 Tools Nghiệp Vụ)

Mọi yêu cầu lấy thông tin đều phải gọi qua MCP Gateway. Mỗi lần gọi thành công sẽ trả về kết quả kèm mã bằng chứng `evidence_ref` định dạng `ev_...`.

| Tên Tool | Tham số chính | Mục đích nghiệp vụ |
| :--- | :--- | :--- |
| `get_policy` | `policy_version` | Lấy bảng quy tắc bồi hoàn, hành động đề xuất và bên chịu trách nhiệm theo chính sách. |
| `get_customer_history` | `customer_unique_id` | Lấy lịch sử tất cả các đơn hàng mà khách hàng này từng đặt. |
| `get_order` | `order_id` | Lấy thông tin cơ bản của đơn hàng (trạng thái, ngày đặt, ngày phê duyệt). |
| `get_order_items` | `order_id` | Lấy danh sách sản phẩm, giá bán, phí ship, mã seller và hạn chót giao cho carrier (`shipping_limit_date`). |
| `get_order_payments` | `order_id` | Chi tiết các giao dịch thanh toán (số đợt, loại thẻ/phiếu, số tiền). |
| `get_payment_timeline` | `order_id` | Mốc thời gian xử lý cổng thanh toán (authorize, capture, status). |
| `get_refund_timeline` | `order_id` | Tiến trình và trạng thái các lệnh hoàn tiền. |
| `get_shipment_summary` | `order_id` | Thông tin giao vận, ngày giao thực tế vs ngày ước tính, đơn vị vận chuyển. |
| `get_sellers` | `seller_id` | Thông tin người bán (địa điểm, trạng thái hoạt động). |
| `get_product_context` | `product_id` | Thông tin danh mục, kích thước, khối lượng sản phẩm. |

> [!IMPORTANT]
> **Quy định nghiêm ngặt về Evidence:**
> - Server tự động lưu audit log mọi lệnh gọi tool của team theo từng `case_id`.
> - Tuyệt đối **không tự bịa đặt mã `evidence_ref`**, không dùng lại evidence giữa các case khác nhau.
> - Bằng chứng đưa vào output bắt buộc phải tồn tại trong audit log của case đó. Vi phạm sẽ dính **Hard Gate (0 điểm)**.

---

## 5. Hợp Đồng Dữ Liệu Input & Output

### 4.1. Cấu trúc Input (`inputs/L3B_CASE_XXX.json`)
```json
{
  "case_id": "L3B_CASE_001",
  "opened_at": "2018-01-01T09:00:00-03:00",
  "customer_request": {
    "language": "vi",
    "message": "Nội dung khiếu nại của khách...",
    "claimed_order_id": "af0bbb47f125381ce9f3597dc70ef07b",
    "claims": [
      {
        "claim_id": "claim-001-a",
        "topic": "late_delivery_logistics"
      }
    ]
  },
  "policy_version": "EC_POLICY_V2",
  "candidate_order_ids": [
    "af0bbb47f125381ce9f3597dc70ef07b",
    "candidate-001"
  ],
  "investigation_scope": {
    "include_customer_history": true,
    "include_product_context": true,
    "require_independent_verification": true
  },
  "customer_unique_id_hint": "customer-597dc70ef07b"
}
```

### 4.2. Cấu trúc Output Bắt Buộc (`outputs/L3B_CASE_XXX.json`)
Tuân thủ schema `contracts/schemas/l3b-output-v2.schema.json`:

```json
{
  "schema_version": "day09-l3b-output-v2",
  "case_id": "L3B_CASE_001",
  "assessment": {
    "primary_issue": "late_delivery_logistics",
    "secondary_issues": [],
    "case_status": "action_required",
    "confidence": 0.95
  },
  "affected_entities": {
    "order_ids": ["af0bbb47f125381ce9f3597dc70ef07b"],
    "item_ids": ["item-001"],
    "seller_ids": ["seller-9b75cdaf2d85"],
    "payment_references": ["pay-001"],
    "shipment_ids": ["ship-001"]
  },
  "claim_assessments": [
    {
      "claim_id": "claim-001-a",
      "verdict": "supported",
      "confidence": 0.95,
      "evidence_refs": ["ev_..."]
    }
  ],
  "entity_resolution": {
    "status": "resolved",
    "resolved_order_ids": ["af0bbb47f125381ce9f3597dc70ef07b"],
    "rejected_candidates": ["candidate-001"],
    "confidence": 0.98
  },
  "customer_context": {
    "customer_unique_id": "customer-597dc70ef07b",
    "related_order_ids": ["af0bbb47f125381ce9f3597dc70ef07b"]
  },
  "shipment_analysis": {
    "verdict": "logistics_delay",
    "late_seller_ids": [],
    "timeline_complete": true
  },
  "payment_analysis": {
    "verdict": "reconciled",
    "captured_total_brl": 150.0,
    "refunded_total_brl": 0.0,
    "refundable_total_brl": 150.0
  },
  "root_cause_analysis": {
    "ranked_causes": [
      {
        "cause_code": "CARRIER_TRANSIT_DELAY",
        "rank": 1
      }
    ],
    "responsible_parties": [
      {
        "party_type": "logistics_provider",
        "party_id": null
      }
    ]
  },
  "evidence_refs": ["ev_4JoBt1Q0...", "ev_wOqnhLD..."],
  "data_conflicts": [],
  "financial_resolution": {
    "currency": "BRL",
    "recommended_refund_brl": 16.0,
    "refund_lines": [
      {
        "reason_code": "freight_refund",
        "amount_brl": 16.0,
        "entity_id": "af0bbb47f125381ce9f3597dc70ef07b"
      }
    ]
  },
  "resolution_actions": [
    "refund_freight"
  ]
}
```

### Các tập giá trị chuẩn (Enums):
- **`primary_issue`**:
  `canceled_order_paid`, `unavailable_order_paid`, `late_delivery_seller`, `late_delivery_logistics`, `valid_split_payment`, `payment_mismatch`, `duplicate_charge`, `refund_pending`, `refund_failed`, `unsupported_claim`, `insufficient_evidence`.
- **`case_status`**:
  `action_required`, `no_action`, `needs_investigation`.
- **`claim_assessment.verdict`**:
  `supported`, `unsupported`, `partially_supported`, `insufficient_evidence`.
- **`entity_resolution.status`**:
  `resolved`, `ambiguous`, `not_found`.
- **`shipment_analysis.verdict`**:
  `on_time`, `seller_delay`, `logistics_delay`, `lost`, `returned`, `conflicting`, `insufficient_evidence`.
- **`payment_analysis.verdict`**:
  `reconciled`, `capture_mismatch`, `duplicate_capture`, `refund_pending`, `refund_failed`, `refunded`, `insufficient_evidence`.
- **`party_type`**:
  `seller`, `platform`, `logistics_provider`, `payment_provider`, `customer`, `unknown`.

---

## 6. Kiến Trúc Multi-Agent & Ghi Vết Trace (`traces/trace.jsonl`)

Luồng xử lý từ lúc nhận case đến khi ra kết quả:
```text
Input Case
    │
    ▼
Coordinator Agent ────────(task_assigned)────────► Entity Resolver Agent
    │                                                     │ (Khớp candidate qua customer history)
    │                                                     ▼
    ├─────────────────────(handoff)──────────────► Specialist Agents
    │                                              - Shipment Specialist (vận chuyển)
    │                                              - Payment Specialist (thanh toán/hoàn tiền)
    │                                                     │ (Gọi MCP tools & thu thập evidence)
    │                                                     ▼
    ├─────────────────────(handoff)──────────────► Policy & Conflict Resolver
    │                                                     │ (Phân giải xung đột, tính bồi hoàn)
    │                                                     ▼
    └─────────────────────(handoff)──────────────► Verifier Agent
                                                          │ (Kiểm tra Schema & Tính nhất quán)
                                                          ▼
                                                   Case Finalized
```

### Các sự kiện Trace bắt buộc (`trace-event-v1`):
1. `case_received`: Coordinator nhận hồ sơ khiếu nại.
2. `task_assigned`: Phân công nhiệm vụ cụ thể cho các Specialist Agent.
3. `tool_result_consumed`: Specialist Agent nhận và sử dụng dữ liệu từ MCP kèm danh sách `evidence_refs`.
4. `handoff`: Bàn giao ngữ cảnh điều tra giữa các Agent.
5. `policy_decided`: Quyết định mức xử lý dựa trên chính sách.
6. `verification_completed`: Verifier hoàn tất kiểm tra tính nhất quán và tính toàn vẹn.
7. `case_finalized`: Coordinator kết thúc case và chuẩn bị ghi file output.

---

## 7. Chính Sách Chấm Điểm & Các Điều Kiện Loại Trực Tiếp (Hard Gates)

### Bảng trọng số tính điểm (Biến thể L3B)

| Hạng mục | Trọng số | Mô tả đánh giá |
| :--- | :---: | :--- |
| **Độ đúng nghiệp vụ (`semantic`)** | **40%** | Kết luận chính xác về vấn đề chính, nguyên nhân, bên chịu trách nhiệm và số tiền. |
| **Chất lượng bằng chứng (`evidence`)** | **15%** | F1-score của các nhóm bằng chứng cần thiết, không gọi thừa domain bị cấm. |
| **Xuất xứ bằng chứng (`provenance`)** | **15%** | 100% `evidence_ref` nộp phải tồn tại trong audit log của server đúng case và team. |
| **Tính nhất quán (`consistency`)** | **10%** | Ràng buộc giữa status, refund amount, resolution actions, và bên chịu trách nhiệm. |
| **Đúng JSON Schema (`schema`)** | **5%** | Tuân thủ tuyệt đối cấu trúc JSON Schema public. |
| **Độ chuẩn xác tự tin (`calibration`)** | **5%** | Điểm tự tin (`confidence`) phản ánh đúng xác suất chính xác của kết luận. |
| **Quy trình Multi-Agent (`workflow`)** | **5%** | Chu trình sự kiện trace đầy đủ, đúng thứ tự, có sự tương tác phối hợp rõ ràng. |
| **Hiệu quả gọi tool (`efficiency`)** | **5%** | Không gọi lặp tool, giữ số lần gọi trong ngân sách cho phép (quá giới hạn sẽ bị suy giảm điểm). |

> [!CAUTION]
> **Các vi phạm dẫn đến 0 ĐIỂM NGAY LẬP TỨC (Hard Gates):**
> 1. `case_id_mismatch`: Sai mã case trong output hoặc trace.
> 2. `unscorable_schema`: File output không vượt qua kiểm tra JSON Schema.
> 3. `missing_required_evidence`: Đưa ra kết luận nhưng thiếu bằng chứng chứng minh.
> 4. `invalid_evidence_refs` / `unknown_evidence_ref`: Mã bằng chứng không đúng định dạng hoặc không có trong log audit MCP.
> 5. `cross_scope_evidence_ref`: Lấy `evidence_ref` của case này điền vào case khác.

---

## 8. Phân Phối Điểm Xếp Hạng
- **20%** dựa trên tập Public (50 case).
- **80%** dựa trên tập Private (50 case).
- Kết quả cuối cùng chọn submission có điểm cao nhất được team xác nhận trên portal.

---

## 9. Kế Hoạch Triển Khai Trong Mã Nguồn

| Bước | Thành phần | File cần thực hiện |
| :---: | :--- | :--- |
| 1 | **Entity Resolver** | `src/student_agent/workflow.py`<br>- Tra cứu `customer_unique_id_hint`<br>- Lọc và xác định `resolved_order_ids` và `rejected_candidates`. |
| 2 | **Shipment Specialist** | `src/student_agent/workflow.py`<br>- Gọi `get_shipment_summary` & `get_order_items`<br>- So sánh `shipping_limit_date` vs `delivered_carrier_date` vs `delivered_customer_date` vs `estimated_delivery_date`. |
| 3 | **Payment Specialist** | `src/student_agent/workflow.py`<br>- Gọi `get_order_payments`, `get_payment_timeline`, `get_refund_timeline`<br>- Tính toán `captured_total_brl`, `refunded_total_brl`, `refundable_total_brl`. |
| 4 | **Policy & Conflict Resolver** | `src/student_agent/workflow.py`<br>- Gọi `get_policy`<br>- Xử lý các điểm xung đột giữa các nguồn dữ liệu vào `data_conflicts`<br>- Xác định `primary_issue`, `root_cause_analysis`, `financial_resolution`. |
| 5 | **Verifier** | `src/student_agent/workflow.py`<br>- Thẩm định các bất biến (invariants) trước khi trả về dictionary kết quả. |
| 6 | **Tài liệu kiến trúc** | `ARCHITECTURE.md`<br>- Điền chi tiết bảng phân quyền Agent, A2A protocol, chính sách xử lý lỗi. |
| 7 | **Chạy & Đóng gói** | Chạy `day09 run`, `day09 validate`, và tạo submission qua `day09 package`. |
