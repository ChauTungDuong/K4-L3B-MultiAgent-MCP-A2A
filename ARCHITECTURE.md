# L3B Architecture Record

Team phải cập nhật tài liệu này cùng source. Mục tiêu là mô tả quyết định có thể kiểm chứng, không ghi prompt bí mật hoặc chain-of-thought.

## 1. System overview

Vẽ hoặc mô tả luồng từ input/candidate resolution đến MCP investigation, specialist agents, conflict resolver, verifier, output và trace.

```text
Input → Entity Resolver → Coordinator → Specialists → Conflict Resolver → Verifier → Output
            │                              │                  │             │
            └──────────────────────────── MCP ────────────────┴──────────── Trace
```

## 2. Agent ownership

| Actor | Input | Trách nhiệm | Tool permission | Output/handoff |
| --- | --- | --- | --- | --- |
| Entity/customer | `customer_unique_id_hint` | Phân giải thực thể, loại trừ candidate. | `get_customer_history` | `resolved_order_ids`, `rejected_candidates` |
| Coordinator | Case payload | Phân phối luồng điều tra. | None | Handoff tasks |
| Order/product | `resolved_order_id` | Trích xuất context đơn hàng và danh sách item. | `get_order`, `get_order_items` | Item list, status |
| Shipment | `resolved_order_id` | Đánh giá giao vận. | `get_shipment_summary` | Shipment verdict |
| Payment/refund | `resolved_order_id` | Đối soát dòng tiền và trạng thái hoàn tiền. | `get_order_payments`, `get_payment_timeline`, `get_refund_timeline` | Payment verdict |
| Policy | `policy_version` | Lấy luật lệ. | `get_policy` | Rules dict |
| Conflict resolver | Evidence | Xử lý mâu thuẫn evidence. | None | Root cause, financial resolution |
| Verifier | Draft output | Thẩm định invariants. | None | Final JSON |

Áp dụng least privilege; tool discovery không đồng nghĩa mọi actor đều được gọi mọi tool.

## 3. Entity resolution và A2A protocol

Cách tiếp cận deterministic (chuyên gia phân tích):
- So khớp candidate_order_ids với customer history order_ids.
- Lọc các candidate dư thừa và xác định resolved_order_id.
- Không lặp lại các calls đã làm, lưu cache evidence (ví dụ _CACHED_POLICY).

## 4. Evidence và conflict lifecycle

- `tool_result_consumed` luôn gắn kèm `evidence_refs`.
- Các evidence_refs được deduplicate cuối quy trình.
- Ưu tiên MCP tools timeline timeline > status > rules để giải quyết mâu thuẫn.

## 5. Failure and efficiency policy

| Failure | Retry budget | Fallback | Trace event/code |
| --- | ---: | --- | --- |
| MCP timeout | 1 | Trả về evidence trống/bỏ qua nhánh nhỏ | `tool_result_consumed` with empty/default |
| Entity not found/ambiguous | 0 | Chọn first candidate | Handoff |
| Source conflict | 0 | Ưu tiên Timeline | Handoff |
| Invalid specialist result | 0 | Dùng mặc định policy | `policy_decided` |

## 6. Verification invariants

- `schema`: Day 09 Output Schema.
- `entity scope`: resolved_order_id mapping với mảng affected_entities.
- `evidence ownership`: 100% trace emit có evidence_refs hợp lệ.

## 7. Reproducibility

- **Giới hạn mô hình (Model Parameter Constraint):** Hệ thống Hybrid / Deterministic Expert Agents (0B) + Qwen2.5-3B-Instruct.
- **Dependency Pinning:** Python 3.11+, `httpx2>=2,<3`, `mcp>=2,<3`, `jsonschema>=4.25,<5`, `python-dotenv>=1.1,<2`.
- **Phần cứng mục tiêu:** Máy trạm Linux/WSL2, GPU hỗ trợ mô hình nhỏ (<= 10B / VRAM 4GB-8GB).
- **Concurrency & Resource Limit:** Điều phối tuần tự từng case theo `case-set.json`, timeout MCP request 30s.
- **Lệnh thực thi chuẩn:**
  ```bash
  source .venv/bin/activate
  day09 run
  day09 validate
  day09 package --output dist/submission.zip
  ```
