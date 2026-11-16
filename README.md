# Nhóm 18 — Hệ thống và Mạng máy tính

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

N18-001 đã được TV4 nghiệm thu theo xác nhận của người dùng ngày 16/11/2026. Các phần mạng mới có bằng chứng kiểm thử được để **Chờ kiểm tra**; giữ TV4 làm reviewer. Gate G1 và các gate khác vẫn phụ thuộc đầu ra tương ứng của cả nhóm. [Bài thử tuần 1](evidence/week1/README.md) được giữ nguyên log gốc.

VM, image, seed, SSH key và runtime không nằm trong Git. Bản kiểm thử trên VM TV1 không thay thế việc TV2 tự chạy lại trên máy của mình. Các phép đo iperf3 trong evidence là kiểm tra hạ tầng, chưa phải kết quả benchmark AI inference.
