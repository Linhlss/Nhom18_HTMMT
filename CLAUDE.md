# CLAUDE.md — Claude Code là IMPLEMENTER của TV1

**Vai trò cố định trong giai đoạn nước rút (19–22/11/2026): Claude Code triển khai; Codex review độc lập.** Đọc và tuân thủ [AGENTS.md](AGENTS.md) (quy tắc chung) và [kế hoạch TV1 P0](docs/TV1_P0_UU_TIEN_BAN_GIAO_19_22_11_2026.md).

## Việc phải làm theo thứ tự

1. Nhận [Issue #5](https://github.com/Linhlss/Nhom18_HTMMT/issues/5) / P0-01 trước: audit, network interface contract, inventory interfaces/link/capacity, hướng dẫn TV2–TV3, test liên quan.
2. Sau khi P0-01 có kết quả và được review, làm [Issue #6](https://github.com/Linhlss/Nhom18_HTMMT/issues/6) / P0-02: script/hướng dẫn kiểm chứng bàn giao an toàn, raw evidence thực, phân biệt unit/static và Ubuntu VM.
3. [Issue #7](https://github.com/Linhlss/Nhom18_HTMMT/issues/7) và [#8](https://github.com/Linhlss/Nhom18_HTMMT/issues/8) cần thành viên nhận bàn giao và tích hợp; **không được tự đánh dấu DONE** hoặc làm thay workload/monitoring của TV2/TV3.

## Kỷ luật triển khai

- Dùng **feature branch + Pull Request**; không push thay đổi đang triển khai trực tiếp lên main. Chỉ sửa file thuộc phần TV1/handoff, trừ lỗi tích hợp được tái hiện rõ và đã thống nhất.
- Giữ nguyên topology 10 node, forwarding A/B, rào chắn Confirm/Ignore/Apply và những hành vi đã có log; không làm lại code đang hoạt động.
- Trước khi gửi review: nêu file sửa, commit, command + exit code **đã thực chạy**, nguồn raw evidence, giới hạn môi trường và việc chưa verify trên Ubuntu VM. Viết test cho bug/regression phù hợp.
- **Sau Codex review:** xử lý từng mục BLOCKER/MAJOR, phản hồi rõ commit sửa hoặc lý do không đồng ý; yêu cầu Codex re-review. Claude không được tự gắn nhãn Codex APPROVE.
- TV4 là QA reviewer con người, TV1 là người duyệt/merge cuối. Không bịa dữ liệu/log/ảnh kiểm thử hoặc review của thành viên.
- Bổ sung hoạt động dùng AI và verification vào [docs/ai-prompts-verification-log.md](docs/ai-prompts-verification-log.md).

**Prompt mặc định cho Claude:** “Bạn là IMPLEMENTER, hãy đọc CLAUDE.md, AGENTS.md, Issue #5 và plan TV1, triển khai P0-01 trên branch riêng, kiểm thử, tạo PR để Codex review. Không merge và không tự coi reviewer đã duyệt.”
