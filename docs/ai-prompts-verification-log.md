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
