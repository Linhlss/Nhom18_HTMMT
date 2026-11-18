# AI Prompts & Verification Log

## Phạm vi và yêu cầu

- Ngày thực hiện: 12/11/2026, múi giờ Việt Nam; log máy kiểm thử ghi UTC.
- Công cụ hỗ trợ: Codex.
- Yêu cầu người dùng: hoàn thiện N18-001 của TV1, tạo Ubuntu 24.04 ARM64 trong UTM, cài Mininet/OVS, lấy log hai host và sau reboot, chuẩn bị bàn giao TV2, commit/push lên GitHub.
- Ràng buộc: dùng dữ liệu chạy thật; N18-001 chỉ ở **Chờ kiểm tra** cho đến khi TV4 review; giữ các task của TV2–TV4 và G1 theo trạng thái thực tế.

## Các yêu cầu dành cho AI khi xây dựng script

1. Setup chỉ chạy trên Ubuntu 24.04 arm64/amd64 với quyền root; dùng APT, kiểm tra Mininet 2.3.x / OVS 3.3.x / Python 3.12.x; chạy lại được.
2. Verify tạo hai host và một OVS bridge, kiểm tra số node/link/port, ping cả hai chiều, trả lỗi khi mất gói và dọn đúng topology vừa tạo.
3. Tạo negative control bằng cách ngắt link h1–s1 trong bài thử; kết quả phải thất bại và cleanup vẫn đạt.
4. Lưu phiên bản, boot ID, timestamp, raw log và JSON kết quả; không tạo dữ liệu đo bằng tay.

Các mục trên tóm tắt yêu cầu đã dùng, không phải bản ghi nguyên văn mọi thông điệp nội bộ.

## Lỗi gặp và cách kiểm chứng bản sửa

| Vấn đề quan sát | Điều chỉnh | Kiểm chứng |
|---|---|---|
| AppleScript không ép được record cấu hình UTM có enum trùng tên | Dùng enum UTM tường minh cho các trường xung đột | Cấu hình UTM xác nhận 4 CPU, 4096 MiB, hypervisor và NAT localhost:2222 |
| `qemu-img` trong framework UTM không phải chương trình CLI chạy trực tiếp | Dùng chức năng Resize của UTM sau khi import image | Header QCow2 và `lsblk` trong guest đều xác nhận 34,359,738,368 byte (32 GiB) |
| Seed gắn CD USB chưa được áp dụng; guest vẫn tên `ubuntu` và không có SSH như yêu cầu | Bổ sung cấu hình mạng NoCloud theo MAC; import seed thành ổ VirtIO chỉ đọc | `cloud-init status --long`: done, không có errors; `DataSourceNoCloud [seed=/dev/vdb]`; hostname `nhom18-w1`, SSH hoạt động |
| Setup ban đầu cài gói thành công nhưng từ chối phiên bản Mininet | `mn --version` ghi stderr; sửa phần kiểm tra để thu cả stdout/stderr | Chạy lại setup: 0 gói mới, kết thúc SETUP PASS; giữ log lần lỗi để đối chiếu |

Không khẳng định riêng nguyên nhân kernel/USB của lỗi seed khi chưa kiểm tra độc lập; kết quả xác nhận là seed trên VirtIO đã được nhận.

## Xác minh mã và kết quả

- `bash -n` cho hai shell script và kiểm tra cú pháp Python đã đạt.
- Setup từ chối chạy native macOS bằng exit code 2, đúng ràng buộc môi trường.
- Setup đã chạy lại trong Ubuntu với 0 gói mới và kết thúc thành công.
- Ping trước và sau reboot: 0% mất gói; mỗi chiều 5/5 gói; cleanup đạt.
- Negative control: mất kết nối, exit code 1, cleanup đạt; đây là lỗi có chủ đích.
- Boot ID trước/sau khác nhau; checksum script lấy từ guest khớp file nguồn trong repo.
- Tracker được cập nhật bằng công cụ spreadsheet và kiểm tra lại sau export: chỉ ba ô K2/L2/N2 của sheet Công việc đổi; công thức, giá trị các task khác, định dạng, validation và conditional formatting được giữ nguyên. Đã xem ảnh render hàng cập nhật và Tổng quan; không thấy lỗi công thức.

Xem [evidence tuần 1](../evidence/week1/README.md) và [checksum mã đã chạy](../evidence/week1/scripts.sha256). Review chéo của TV4 và việc tái lập trên Windows/Mac Intel chưa được thực hiện trong phiên này. Các số RTT trong raw log chỉ mô tả bài thử VM, chưa được dùng làm kết quả nghiên cứu A/B.

## Bổ sung ngày 16/11/2026 — hoàn thiện hạ tầng TV1

### Yêu cầu và quyết định

- Người dùng yêu cầu hoàn thiện topology/routing/firewall, profile A/B và Apply để bàn giao cho TV2, commit/push lên repo. Người dùng xác nhận TV4 đã nghiệm thu N18-001.
- Kế hoạch được người dùng yêu cầu triển khai: 10 node; A single-path; B phân luồng tĩnh theo client subnet; operator Confirm/Ignore; verify, rollback khi thao tác thất bại; kiểm thử trước/sau reboot và clone sạch.
- Người dùng chọn chỉ đưa hạ tầng và gói bàn giao lên repo, giữ bộ báo cáo LaTeX/PDF trên máy.
- Không làm thay workload, dashboard hoặc detection/analysis của TV2–TV3; fixture TCP và iperf3 chỉ phục vụ kiểm thử mạng.

Các dòng trên tóm tắt yêu cầu và quyết định trong phiên, không phải bản chép mọi trao đổi nội bộ.

### Lỗi gặp và cách kiểm chứng bản sửa

| Quan sát thực tế | Bản sửa | Kiểm chứng |
|---|---|---|
| `ovs-ofctl barrier` không phải subcommand của bản cài đặt | Bỏ lời gọi không hợp lệ; soát flow dump sau `replace-flows` | Runtime khởi động và bộ soát rule đạt |
| Mã chép vào VM bằng archive không có `.git`, metadata làm bộ test dừng | Cho phép metadata Git trống; SHA256 source manifest luôn bắt buộc | Bản archive chạy đủ bộ; clone sạch có commit thực |
| `tc` không thấy `c1-eth0` ở root namespace | Đọc interface host qua namespace của host | Cả 20 interface đều được kiểm tra rate thực tế |
| Counter OVSDB bằng 0 trong probe ngắn dù capture có packet | Dùng counter kernel trực tiếp trên interface/OVS port tương ứng | PCAP + delta RX/TX đồng nhất ở ba lượt A/B |
| Chương trình TCP timeout in stderr nhưng returncode bị trả 0 | Không dùng detach kép: Python tạo session, Mininet dùng `mnexec -a` | Lệnh `exit 7` trả 7; TCP/9000 bị chặn trả thất bại; bộ test không chấp nhận false success |
| Lặp stop/start gặp socket cũ chưa kịp giải phóng | `stop` chờ socket và owner lock được giải phóng trước khi trả | Hai vòng start/verify/stop bổ sung đều đạt ở cả hai boot |
| So sánh font bằng StyleProxy báo khác dù hình và thuộc tính giống | So sánh bản sao đối tượng style thay vì proxy | Không có thay đổi font/fill/alignment/border/protection ngoài phạm vi |

Log các lần test thất bại được giữ nguyên trong [evidence mạng](../evidence/network/README.md); không đổi cờ thất bại thành PASS. HTB có cảnh báo quantum trong runtime log; bộ test vẫn yêu cầu lệnh thành công, class rate đúng và số liệu chẩn đoán thực, không bỏ qua lỗi bằng cách lọc stderr.

### Kết quả xác minh

- 10 unit tests cho topology, hướng chuyển tiếp, ARP không vòng lặp, soát rule/counter, xác nhận/Ignore, idempotency và rollback.
- Bộ đầy đủ trước reboot: 33 checks PASS; sau reboot: 33 checks PASS, boot ID khác nhau, checksum nguồn của hai lượt khớp code commit `084189b5d27eeec5fdb2fa6edb13a634316b7c5c`.
- Clone sạch từ Git bundle của cùng commit trong thư mục mới: setup chạy lại thành công, 10 unit tests và 8 kiểm tra quick PASS; source manifest của cả ba lượt đạt được so trực tiếp với Git blob trong commit.
- Ping verify hai chiều 3/3, probe từng đường 40/40; ba lượt kiểm chứng mỗi profile bằng capture và counter.
- Firewall được kiểm tra với server thực sự mở cả cổng cho phép và cổng chặn. Ngắt đường Spine 2 làm Apply B thất bại và khôi phục A được xác minh lại.
- Các phép đo iperf3 8 kết nối cho kết quả được giữ trong raw JSON, không được trình bày như benchmark workload AI inference.
- Tracker được author bằng Artifact Tool: 40 ô trạng thái/link/ghi chú thay đổi; mọi giá trị/công thức khác và style giữ nguyên, không mất ZIP part, số conditional-format/validation/extLst giữ nguyên. Đã recalculate, quét lỗi công thức và xem ảnh render vùng thay đổi/Tổng quan.
- N18-001 hoàn thành theo xác nhận người dùng; các task mạng mới chờ TV4 review. Chưa xác minh cài mới Ubuntu trên OS sạch hoặc chạy trên máy thành viên khác; N18-041/N18-045 không được báo hoàn thành.

Hướng dẫn tích hợp và phạm vi: [bàn giao TV2](network-handoff.md). Commit chứa mã hạ tầng: `084189b5d27eeec5fdb2fa6edb13a634316b7c5c`; commit bổ sung tài liệu/minh chứng được lưu trong lịch sử Git khi xuất bản.

## Bổ sung ngày 18/11/2026 — hoàn thiện tuần 1 cho TV2, TV3, TV4

### Yêu cầu và quyết định

- Công cụ: Claude Code (Opus 5.5), phiên làm việc trong worktree nhánh `claude/complete-week1-n18-3fc6c1`.
- Người dùng dán kế hoạch “Hoàn thiện tuần 1 cho TV2, TV3 và TV4 trong 2 ngày làm việc” và yêu cầu xem xét kỹ, thực hiện các công việc theo checklist. Bản nháp v0 của ba thành viên là PDF trong thư mục “Sản phẩm của 3 thành viên còn lại” (không đưa vào Git).
- Quyết định giữ trung thực: bài thử chạy trên VM `Nhom18-W1` của TV1 và ghi đúng máy; không coi là TV2/TV3/TV4 tự chạy; không điền thay review của thành viên; N18-002/003/004 chỉ ở **Chờ kiểm tra**, G1 chưa chốt; không sửa evidence cũ của TV1.
- Cấu hình workload dùng JSON (Python hệ thống Ubuntu không có YAML sẵn).

Các dòng trên tóm tắt yêu cầu và quyết định, không phải bản chép nguyên văn mọi trao đổi.

### Mã do AI hỗ trợ viết

`workload/` (framing, protocol, config, client, server, smoke_test), `measurement/` (week1_probe, to_csv), `qa/check_week1_logs.py`, `tools/` (evidence, stats), `tests/test_workload.py`, `tests/test_measurement.py`.

### Lỗi gặp và cách kiểm chứng bản sửa

| Quan sát thực tế | Điều chỉnh | Kiểm chứng |
|---|---|---|
| Bản nháp cho phép size ≥ 128 B; metadata request/response dài nhất cần 474/529 B | Ngưỡng tối thiểu tính trực tiếp từ hàm tạo metadata; encode báo lỗi khi thiếu chỗ | Unit test `test_size_below_metadata_rejected`, `test_size_too_small_is_an_error` |
| Unit test để lại socket/file chưa đóng (ResourceWarning) | Đóng socket bằng `addCleanup`, đọc CSV bằng context manager | `python3 -W error::ResourceWarning -m unittest` không cảnh báo |
| Checker so min/mean ping bằng tuyệt đối, KHÔNG ĐẠT trên dữ liệu thật (F1) | Dung sai ±0,005 ms do ping làm tròn từng reply | Lượt kiểm tra lại ĐẠT; ghi metrics-spec §5.3 |
| iperf3 3.16 báo interval đầu sau `-O` có `seconds≈2,0`, converter tính khoảng đo 11,0 s (F2) | Dùng `end.sum_*`; cột `timing_suspect`; đối chiếu byte với `sum_sent` | Test `test_iperf3_post_omit_interval_flagged`; lượt TV3 rerun và checker ĐẠT |

### Kết quả xác minh

- macOS: 30 unit test OK (gồm loopback client/server và 2 ca lỗi). VM: 30 unit test OK, log tại `evidence/tv4-week1/20261118T113030251138Z-unit-tests/`.
- TV2: 2 lượt `smoke_test.py --negative` PASS (10/10 OK, 3/3 ca âm tính đúng mã). TV3: 2 lượt `week1_probe.py` PASS (lượt đầu có lỗi CSV F2, giữ nguyên). TV4: checker lần đầu 22/24, sau sửa 25/25.
- `source-manifest.json` của 4 lượt TV2/TV3 khớp Git blob của commit tương ứng (`6d7df69`, `af83849`).
- Tracker: chỉ đổi 9 ô K/L/N hàng N18-002…004 sheet `Công việc` bằng sửa XML trực tiếp; các phần khác của file xlsx giữ nguyên byte (xem commit).
- Chưa làm: chạy trên máy thành viên khác; review/phê duyệt của TV1–TV3; tạo issue/board trên GitHub.
