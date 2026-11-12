# Nhóm 18 — Hệ thống mạng máy tính

Prototype giám sát, đánh giá cấu hình mạng Data Center Spine–Leaf cho lưu lượng AI inference giả lập, dùng Mininet/Open vSwitch trong Ubuntu VM.

## Bàn giao tuần 1: TV1 → TV2

Phần kỹ thuật môi trường của TV1 đã kiểm thử hai host thành công, gồm chạy lại sau reboot. **N18-001: Chờ kiểm tra bởi TV4**. Gate G1 còn cần các đặc tả của TV2–TV4.

- [Môi trường, hướng dẫn cài đặt và đầu việc TV2](docs/env-matrix.md)
- [Kết quả và minh chứng tuần 1](evidence/week1/README.md)
- [Phân công 12 tuần](Nhom18_Phan_cong_Checklist_12_tuan.md)
- [Bảng tiến độ](Nhom18_Progress_Tracker.xlsx)
- [Đề cương và bộ tài liệu gốc](README_BAT_DAU.md)
- [AI Prompts & Verification Log](docs/ai-prompts-verification-log.md)

Trong **Ubuntu 24.04 VM** đúng kiến trúc:

```bash
git clone https://github.com/Linhlss/Nhom18_HTMMT.git
cd Nhom18_HTMMT
sudo bash scripts/setup-ubuntu.sh
sudo bash scripts/verify-week1.sh --label tv2-local
```

TV2 bắt đầu N18-002: đặc tả kích thước request/response, rate, concurrency và service delay. Code workload/client/server thuộc phần việc của TV2. Bài thử tuần 1 chỉ có hai host và một switch; topology 10 node và thực nghiệm A/B thuộc các tuần sau.

VM, image và khóa SSH không nằm trong repo. Mỗi người tự dựng VM, lưu log thực tế và nhờ thành viên khác review trước khi đánh dấu hoàn thành.
