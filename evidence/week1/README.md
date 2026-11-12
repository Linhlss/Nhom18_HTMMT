# Minh chứng tuần 1 — TV1 / N18-001

**Kết quả kỹ thuật:** đạt bài thử môi trường hai host. **Trạng thái nghiệm thu: Chờ kiểm tra bởi TV4.**

Thực hiện ngày 12/11/2026. Timestamp trong tên thư mục và log dùng UTC (giờ Việt Nam = UTC + 7).

## Kết quả chạy thực tế

| Lần chạy | Kết quả kết nối | Cleanup | Exit code | Bằng chứng |
|---|---|---|---:|---|
| before-reboot | Đạt: pingall 0% mất gói, hai chiều đều 5/5 | Đạt | 0 | [JSON](20261112T082215606840279Z-before-reboot/result.json), [raw log](20261112T082215606840279Z-before-reboot/run.log), [môi trường](20261112T082215606840279Z-before-reboot/environment.json), [packages](20261112T082215606840279Z-before-reboot/packages.tsv) |
| negative-control | Thất bại có chủ đích: ngắt link h1–s1, pingall mất 100% | Đạt | 1 | [JSON](20261112T082255786936106Z-negative-control/result.json), [raw log](20261112T082255786936106Z-negative-control/run.log), [môi trường](20261112T082255786936106Z-negative-control/environment.json), [packages](20261112T082255786936106Z-negative-control/packages.tsv) |
| after-reboot | Đạt: pingall 0% mất gói, hai chiều đều 5/5 | Đạt | 0 | [JSON](20261112T082353858808544Z-after-reboot/result.json), [raw log](20261112T082353858808544Z-after-reboot/run.log), [môi trường](20261112T082353858808544Z-after-reboot/environment.json), [packages](20261112T082353858808544Z-after-reboot/packages.tsv) |

Boot ID trước reboot: `87569009-6bba-43e6-83b4-aad7548b8bf2`. Sau reboot: `53bdbe50-4b5f-4c9f-b382-1b399ba34d9c`. Hai boot ID khác nhau; OVS/SSH và bài thử hai host vẫn hoạt động sau reboot.

## Môi trường và nguồn mã

- Ubuntu 24.04.5 LTS ARM64; kernel 6.8.0-147-generic; Python 3.12.3.
- Mininet 2.3.0-1.1; Open vSwitch 3.3.9-0ubuntu0.24.04.1.
- [Cấu hình VM](vm-config.json), [kết quả cloud-init và ổ đĩa](provisioning.txt), [nguồn image và SHA256](image-source.json).
- [Setup thành công khi chạy lại](setup.log); [log setup ban đầu trước khi sửa cách đọc phiên bản](setup-initial-failed.log). Lần setup sau cài thêm 0 gói.
- [SHA256 của các script thực sự đã chạy trong guest](scripts.sha256).

## TV4 kiểm tra và TV2 sử dụng

1. Đọc [ma trận môi trường và hướng dẫn bàn giao](../../docs/env-matrix.md).
2. Kiểm tra raw log, JSON, packages và checksum; chạy lại verify trong Ubuntu 24.04 đúng kiến trúc.
3. TV4 ghi nhận review thực tế rồi mới đổi N18-001 thành Hoàn thành.
4. TV2 bắt đầu N18-002 về đặc tả workload; G1 chưa được chốt chỉ từ bài thử này.

**Giới hạn:** mới chạy thực tế trên Mac ARM/UTM; chưa chạy trên Mac Intel hoặc Windows. Chưa triển khai topology 10 node, workload hoàn chỉnh, profile A/B hay benchmark hiệu năng AI. Negative control là kiểm thử cơ chế báo lỗi, không phải kết quả kết nối đạt.
