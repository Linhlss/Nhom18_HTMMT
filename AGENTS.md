# AGENTS.md — Nhóm 18 HTMMT (Codex / coding agents)

## Thứ tự đọc bắt buộc (19–22/11/2026)

1. **[TV1 P0 — ưu tiên bàn giao cho TV2–TV4](docs/TV1_P0_UU_TIEN_BAN_GIAO_19_22_11_2026.md)**: triển khai **P0-01 trước, P0-02 sau**. P0-03 cần người nhận tự chạy; P0-04 cần runner TV2 + collector TV3. Không mặc nhiên đánh dấu đã hoàn thành.
2. [Handoff network hiện có](docs/network-handoff.md), [topology model](topology/model.py), [runtime](topology/runtime.py), [networkctl](control/networkctl.py), [evidence network](evidence/network/README.md).
3. [Workload spec TV2](docs/workload-spec.md), [Metrics spec TV3](docs/metrics-spec.md), [QA rubric TV4](docs/scope-rubric.md), [12-week checklist](Nhom18_Phan_cong_Checklist_12_tuan.md).

## Mục tiêu và phạm vi

TV1 là nhóm trưởng/Network Lead, nhưng **chỉ sở hữu module network + interface bàn giao + hỗ trợ QA và quyết định kỹ thuật**. TV2 làm workload/dashboard, TV3 làm monitoring/detect/recommend/compare, TV4 QA/báo cáo. Làm song song. Còn 3–5 tuần, tối ưu đường găng; không làm hộ module người khác.

Hệ thống là **Mininet/Open vSwitch 10 node trong Ubuntu 24.04 VM**, workload **AI-inference-like giả lập** không GPU, không LLM, không API trả phí. Profile A single-path; B phân luồng OpenFlow tĩnh theo subnet client (**không gọi ECMP**). **Không self-healing**; Apply chỉ sau xác nhận rõ ràng của operator.

## Quy tắc thay đổi

- **Đọc code HEAD và tests trước khi sửa**; không rewrite topology/Apply có bằng chứng chỉ để “hoàn thiện”; giữ backward compatibility với TV2/TV3.
- Mỗi thay đổi nhỏ có unit test; integration test cần chạy **trong Ubuntu VM**. Không ghi “VM pass” nếu agent không chạy được trên VM; không tạo raw measurement, ảnh hoặc logs giả. Không sửa/xóa raw evidence lịch sử.
- Interface capacity lấy **tc/HTB shaping**, không lấy speed của OVS veth. Counter đọc từ đúng interface và đúng network namespace; xem docs/metrics-spec.md.
- Không chạy `mn -c` tùy tiện, không stop hay xóa testbed người khác, không expose root-only local socket ra HTTP. Không bypass explicit Confirm/Ignore/Apply, không tự động Apply khi benchmark đang chạy.
- Không trộn iperf3 diagnostic với workload AI inference benchmark. Đối chứng A/B giữ cùng offered load và cấu hình; cần path counters/PCAP xác minh.
- Chỉ cập nhật checklist/task lên **Hoàn thành** sau khi có code, log/test và reviewer khác xác nhận. Ghi AI prompts + validation vào `docs/ai-prompts-verification-log.md`.

## Lệnh tham khảo, không báo là đã chạy khi chưa chạy

```bash
python3 -m unittest discover -s tests -v
sudo bash scripts/setup-ubuntu.sh
sudo /usr/bin/python3 scripts/verify-network.py --label tv1-handoff
sudo /usr/bin/python3 control/networkctl.py start --profile A
sudo /usr/bin/python3 control/networkctl.py status
sudo /usr/bin/python3 control/networkctl.py verify
sudo /usr/bin/python3 control/networkctl.py stop
```

Chạy `verify-network.py` trên Ubuntu VM khi không có testbed khác đang hoạt động.

## Báo cáo sau mỗi task

Nêu: task ID, file thay đổi, lệnh đã thực sự chạy + exit code, môi trường, evidence/link, rủi ro/chưa xác minh, người nhận bàn giao. Không tự merge vào main khi chưa review.
