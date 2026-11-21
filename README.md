# Nhóm 18 — Hệ thống và Mạng máy tính

> **🚨 ƯU TIÊN NGAY — TV1 (NHÓM TRƯỞNG), 19–22/11/2026:** [MỞ CHECKLIST P0 BÀN GIAO CHO CODEX / CLAUDE](docs/TV1_P0_UU_TIEN_BAN_GIAO_19_22_11_2026.md). Thực hiện **P0-01 → P0-02 trước**, sau đó TV2/TV3 tự chạy kiểm chứng (P0-03) và nhóm tích hợp pilot (P0-04). **Đây là việc cần làm, chưa được nghiệm thu.** **Claude Code triển khai, Codex chỉ review PR**; đọc [AGENTS.md](AGENTS.md) và [CLAUDE.md](CLAUDE.md); không viết lại hạ tầng đã có và không làm thay phần TV2–TV4. Hạn ưu tiên: **gói code/tài liệu TV1 ngày 20/11; pilot chung 22/11**.

**Issue theo thứ tự:** [#5 — Contract & inventory](https://github.com/Linhlss/Nhom18_HTMMT/issues/5) → [#6 — Verify/handoff](https://github.com/Linhlss/Nhom18_HTMMT/issues/6) → [#7 — TV2/TV3 tự chạy](https://github.com/Linhlss/Nhom18_HTMMT/issues/7) → [#8 — Pilot A/B chung](https://github.com/Linhlss/Nhom18_HTMMT/issues/8). **Claude nhận #5 trước; Codex review PR #5 rồi #6**, không tự đánh dấu #7–#8 DONE.

## TV2–TV4 — Issues P0 nước rút (bắt đầu song song, 21/11/2026)

| Người phụ trách | Issue đầu mối | Bàn giao ưu tiên |
|---|---|---|
| **TV2** | [#9 — Workload/Runner/Dashboard/Demo](https://github.com/Linhlss/Nhom18_HTMMT/issues/9) | Runner 1/2/4/8 flows và raw log → dashboard/UI |
| **TV3** | [#10 — Collector/Detect/Recommend/Compare](https://github.com/Linhlss/Nhom18_HTMMT/issues/10) | Metric theo link/cửa sổ → cảnh báo, khuyến nghị, so sánh |
| **TV4** | [#11 — QA/Report/Slides](https://github.com/Linhlss/Nhom18_HTMMT/issues/11) | QA độc lập song song → nghiệm thu E01–E10, báo cáo 2 chương |

**Mốc đề xuất:** 28/11 pilot workload + collector; 05/12 nguyên mẫu end-to-end; 12/12 thí nghiệm/báo cáo/demo tối thiểu. Giữ các Issues [#7](https://github.com/Linhlss/Nhom18_HTMMT/issues/7) (tự kiểm tra VM) và [#8](https://github.com/Linhlss/Nhom18_HTMMT/issues/8) (pilot A/B) làm **điểm tích hợp chung**, không tạo nhiệm vụ trùng. Mốc phải điều chỉnh theo hạn nộp thực tế của môn học.

Prototype giám sát, đánh giá cấu hình mạng Data Center Spine–Leaf cho lưu lượng AI inference giả lập, dùng Mininet/Open vSwitch trong Ubuntu VM.

## Gói hạ tầng TV1 → TV2

Đã triển khai topology **10 node**, routing/gateway/firewall, profile A single-path, profile B phân luồng tĩnh qua hai spine và CLI Apply/Ignore có xác nhận. Phần workload, dashboard và monitoring/analysis của TV2–TV3 tiếp tục phát triển trên hạ tầng này.

- [Hướng dẫn bàn giao và giao diện CLI/JSON cho TV2](docs/network-handoff.md)
- [Minh chứng kiểm thử mạng và giới hạn nghiệm thu](evidence/network/README.md)
- [Môi trường, cách dựng Ubuntu VM](docs/env-matrix.md)
- [Phân công 12 tuần](Nhom18_Phan_cong_Checklist_12_tuan.md)
- [Bảng tiến độ](Nhom18_Progress_Tracker.xlsx)
- [AI Prompts & Verification Log](docs/ai-prompts-verification-log.md)
- [Bộ đề cương gốc](README_BAT_DAU.md)

## Tuần 1 — đặc tả và bài thử của TV2, TV3, TV4

| Task | Tài liệu | Mã | Minh chứng | Trạng thái |
|---|---|---|---|---|
| N18-002 (TV2) | [workload-spec.md](docs/workload-spec.md) | [workload/](workload/) | [evidence/tv2-week1](evidence/tv2-week1/README.md) | Hoàn thành (TV3 đã review) |
| N18-003 (TV3) | [metrics-spec.md](docs/metrics-spec.md) | [measurement/](measurement/) | [evidence/tv3-week1](evidence/tv3-week1/README.md) | Hoàn thành (TV1 đã review) |
| N18-004 (TV4) | [scope-rubric.md](docs/scope-rubric.md) | [qa/](qa/) | [evidence/tv4-week1](evidence/tv4-week1/README.md) | Hoàn thành (TV2 đã review, TV1 phê duyệt) |

Biên bản review: [qa/week1-review.md](qa/week1-review.md). Review chéo đã đạt và **G1 đã chốt** theo xác nhận của nhóm trưởng TV1 ngày 18/11/2026. Bài thử tuần 1 chạy trên VM của TV1; lệnh để mỗi thành viên chạy lại trên máy của mình:

```bash
python3 -m unittest discover -s tests -v
sudo /usr/bin/python3 control/networkctl.py start --profile A
sudo /usr/bin/python3 workload/smoke_test.py --label tv2-smoke --negative
sudo /usr/bin/python3 measurement/week1_probe.py --label tv3-probe
sudo /usr/bin/python3 control/networkctl.py stop
python3 qa/check_week1_logs.py --tv2 evidence/tv2-week1/<run> --tv3 evidence/tv3-week1/<run> --out evidence/tv4-week1/<UTC>-tv4-logcheck
```

Trong **Ubuntu 24.04 VM** đúng kiến trúc:

```bash
git clone https://github.com/Linhlss/Nhom18_HTMMT.git
cd Nhom18_HTMMT
sudo bash scripts/setup-ubuntu.sh
python3 -m unittest discover -s tests -v
sudo /usr/bin/python3 control/networkctl.py start --profile A
sudo /usr/bin/python3 control/networkctl.py verify
sudo /usr/bin/python3 control/networkctl.py status
```

`exec` chạy chương trình trong namespace host. TV2 dùng `a1=10.18.3.11`, `a2=10.18.3.12`, TCP cổng 8000; phân kết nối luân phiên giữa c1/c2 để profile B sử dụng cả hai đường. Chương trình client/server AI inference sẽ do TV2 viết.

```bash
# Sau khi dừng các lệnh workload và người vận hành xác nhận:
sudo /usr/bin/python3 control/networkctl.py apply --profile B --decision apply --confirm --actor TV2
sudo /usr/bin/python3 control/networkctl.py stop

# Bộ kiểm thử tự dựng/dọn topology, chỉ chạy khi chưa có testbed đang hoạt động:
sudo /usr/bin/python3 scripts/verify-network.py --label tv2-local
```

N18-001 đã được TV4 nghiệm thu theo xác nhận của người dùng ngày 16/11/2026. Các task hạ tầng N18-005/009/013/017/021/025/029/033/037 đã được TV4 review và chuyển **Hoàn thành** theo xác nhận của nhóm trưởng TV1 ngày 18/11/2026; N18-041 vẫn **Đang làm**. G1 đã chốt; các gate sau vẫn phụ thuộc đầu ra tương ứng của cả nhóm. [Bài thử tuần 1](evidence/week1/README.md) được giữ nguyên log gốc.

VM, image, seed, SSH key và runtime không nằm trong Git. Bản kiểm thử trên VM TV1 không thay thế việc TV2 tự chạy lại trên máy của mình. Các phép đo iperf3 trong evidence là kiểm tra hạ tầng, chưa phải kết quả benchmark AI inference.
