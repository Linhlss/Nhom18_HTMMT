# Minh chứng hạ tầng TV1 — bàn giao TV2

Ngày thực hiện: **16/11/2026**. Timestamp trong tên thư mục/log dùng UTC. Môi trường thực tế: Mac ARM → UTM `Nhom18-W1` → Ubuntu 24.04 ARM64; cấu hình và phiên bản thực tế nằm trong `environment.json` của mỗi lượt.

## Các lượt nghiệm thu kỹ thuật

| Lượt | Kết quả | Chi tiết |
|---|---|---|
| Trước reboot, bản cuối | **PASS, 33 kiểm tra** | [result.json](20261116T132432534717Z-before-reboot-final/result.json), [environment](20261116T132432534717Z-before-reboot-final/environment.json), [mã đã chạy](20261116T132432534717Z-before-reboot-final/source-manifest.json) |
| Sau reboot | **PASS, 33 kiểm tra** | [result.json](20261116T132840630580Z-after-reboot/result.json), [environment](20261116T132840630580Z-after-reboot/environment.json), [mã đã chạy](20261116T132840630580Z-after-reboot/source-manifest.json) |
| Clone sạch của commit hạ tầng | **PASS, 8 kiểm tra quick + 10 unit tests** | [result.json](20261116T133228480187Z-clean-clone/result.json), [environment](20261116T133228480187Z-clean-clone/environment.json), [log clone/setup/unit tests](clean-clone.log) |

Boot ID trước reboot: `53bdbe50-4b5f-4c9f-b382-1b399ba34d9c`; sau reboot: `2a2fd532-0d9a-4069-83bc-ba94de68a743`. Hai lượt chạy đủ bộ có cùng checksum nguồn, khớp mã được commit tại **084189b5d27eeec5fdb2fa6edb13a634316b7c5c**.

Các điều kiện đã xác minh:

- 6 host/namespace, 4 OVS switch, 10 link; 20 interface được cấu hình đúng rate; IP/route/port mapping được lưu trong log.
- Tám hướng client↔server đều nhận đủ 3/3 ping khi verify. Mỗi lượt kiểm chứng đường đi còn có 40/40 ping cho c1→a1 và c2→a2; không suy luận từ một chuỗi “PASS”.
- A/B được kiểm chứng bằng PCAP và delta byte/packet counter, ba lượt mỗi profile. A chỉ có IPv4 probe qua Spine 1; B có c1 qua Spine 1 và c2 qua Spine 2. Xem các file `a-*-paths.json`, `b-*-paths.json`, PCAP và bản decode cạnh chúng.
- Firewall cho phép TCP/8000, chặn TCP/9000 khi server thực sự lắng nghe cả hai cổng; counter DROP tăng. Xem `firewall.json`.
- Ignore, Apply thiếu xác nhận, profile sai và Apply khi đang chạy workload đều không thay đổi flow table.
- Ngắt `leaf1-eth3` có chủ đích làm Apply B trả thất bại; khôi phục A và verify lại thành công. Đây là **negative case đạt kỳ vọng**, không phải lần kết nối B thành công. Xem `negative-apply.json`.
- Lệnh `exit 7` trong c1 được giữ đúng returncode 7 và báo thất bại; kiểm tra hồi quy cho lỗi mã thoát của `mnexec`.
- Dừng/tạo lại topology nhiều lượt, kiểm tra không còn bridge/interface do phiên thử tạo. Reboot giữ được package và mã nguồn, sau đó testbed được dựng lại bằng lệnh `start`.

## Phép đo chẩn đoán hạ tầng

Mỗi cấu hình chạy hai tiến trình iperf3 đồng thời: c1→a1 và c2→a2, mỗi tiến trình 4 kết nối TCP; tổng 8 kết nối, thời lượng đo 5 giây, bỏ qua 1 giây đầu. Giữ cùng tham số A/B; số liệu lấy từ `sum_received` của iperf3.

| Lượt | A tổng nhận (Mbps) | B tổng nhận (Mbps) |
|---|---:|---:|
| Trước reboot | 23.906 | 47.175 |
| Sau reboot | 23.993 | 47.887 |

Raw output ở `capacity-a.json` và `capacity-b.json` của từng lượt. Kết quả B vượt 40 Mbps trong phép thử này, phù hợp với hai đường fabric 25 Mbps/link và các link biên 100 Mbps. Đây là kiểm tra hạ tầng ở tải đã thử; không chứng minh gateway/firewall sẽ không nghẽn với mọi workload.

Counter ngắn hạn được đọc trực tiếp bằng `ip -s -j link` trên các interface tương ứng OVS port, tránh độ trễ cập nhật `Interface.statistics` trong OVSDB. Rule dump và PCAP được dùng cùng counter để xác minh đường đi.

**Các phép đo này không phải benchmark AI inference**, không thay kết quả RQ1–RQ3. Workload request/response, monitoring/detection/recommendation và dashboard vẫn thuộc TV2–TV3.

## Setup và tái lập

[Setup chạy lại](setup-rerun.log) kết thúc thành công, không cài thêm gói mới. Clone sạch được kiểm tra riêng từ Git bundle của commit hạ tầng; [verification-summary.json](verification-summary.json) xác nhận checksum cả ba lượt đạt khớp mã trong commit. Clone sạch trên cùng VM không phải cài mới Ubuntu và không phải kiểm thử trên máy của thành viên khác.

## Lịch sử lỗi khi phát triển

Các thư mục trước bản cuối được giữ nguyên, có `success: false` và exit code 1:

| Timestamp UTC | Lỗi được ghi nhận | Bản sửa |
|---|---|---|
| 13:15:42 | Bản mã chép bằng archive không có `.git` | Metadata cho phép thiếu Git; dùng source manifest làm định danh |
| 13:18:01 | Đọc `tc` của host từ root namespace | Thu `tc` trong đúng namespace của host |
| 13:19:01 | OVSDB counter chưa refresh trong probe ngắn | Đọc kernel interface counter trực tiếp |
| 13:20:22 | TCP bị chặn nhưng tiến trình báo returncode 0 | Bỏ detach kép: dùng `mnexec -a` với session do Python tạo |
| 13:21:59 | Restart trước khi socket/owner lock được giải phóng | Chờ shutdown hoàn tất trong API `stop` |

Không tính các lượt này vào hai bộ nghiệm thu đạt. Mỗi thư mục có source manifest riêng để đối chiếu đúng phiên bản khi lỗi xảy ra.

## Trạng thái bàn giao

- **N18-001: Hoàn thành**, theo xác nhận TV4 đã nghiệm thu của người dùng ngày 16/11/2026.
- **N18-005/009/013/017/021/025/029/033/037: Chờ kiểm tra**, có mã và minh chứng kỹ thuật; TV4 vẫn là reviewer.
- **N18-041: Đang làm**, đã có script/setup chạy lại và kiểm tra clone sạch trên VM hiện có; còn xác minh cài mới Ubuntu.
- **N18-045:** cần lần chạy thật trên máy thành viên khác. TV2 có thể bắt đầu nhận gói và chạy xác minh ngay.
- Giữ trạng thái các task TV2–TV4 và gate còn phụ thuộc chúng; không coi hạ tầng đạt là toàn prototype hoàn thành.

Hướng dẫn sử dụng: [docs/network-handoff.md](../../docs/network-handoff.md).
