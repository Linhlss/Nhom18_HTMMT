# Môi trường tuần 1 và bàn giao TV2

**Task:** N18-001 — TV1. **Người review:** TV4.  
Tài liệu này chuẩn hóa môi trường và bài thử khởi động hai host. Topology Spine–Leaf 10 node thuộc các tuần sau.

## 1. Ma trận môi trường

| Máy thật | Phương án VM | Guest Ubuntu | Trạng thái kiểm chứng |
|---|---|---|---|
| Mac Apple Silicon, macOS 26.7.3 | UTM 4.7.4, QEMU ARM64, hypervisor bật | Ubuntu 24.04.5 LTS arm64 | Bài thử hai host đã đạt; xem evidence cho các lần chạy |
| Mac Intel | UTM, guest x86_64 với tăng tốc phần cứng phù hợp | Ubuntu 24.04 LTS amd64 | Phương án đối chiếu tài liệu; chưa chạy trên máy Intel |
| Windows Intel/AMD 64-bit | VirtualBox, bật VT-x/AMD-V, NAT | Ubuntu 24.04 LTS amd64 | Phương án đối chiếu tài liệu; chưa chạy trên Windows |

Cấu hình thống nhất: **4 vCPU, 4 GiB RAM, đĩa 32 GiB**. Không dùng chung image ARM64 và AMD64. Các máy dùng cùng nhánh Ubuntu 24.04 và script thiết lập; phiên bản gói đầy đủ phải được lưu lại vì số revision có thể khác giữa kiến trúc hoặc thời điểm cập nhật.

| Thành phần | Nhánh yêu cầu | Cách xác minh |
|---|---|---|
| Ubuntu | 24.04 LTS | `cat /etc/os-release` |
| Kiến trúc guest | `aarch64` hoặc `x86_64` | `uname -m`; `dpkg --print-architecture` |
| Python hệ thống | 3.12.x | `/usr/bin/python3 --version` |
| Mininet | 2.3.x từ Ubuntu Universe | `mn --version` |
| Open vSwitch | 3.3.x từ Ubuntu | `ovs-vsctl --version` |
| Công cụ đo | iproute2, iputils-ping, iperf3, tcpdump | `packages.tsv` của mỗi lần kiểm thử |

Phiên bản thực tế trên VM TV1: kernel **6.8.0-147-generic**, Python **3.12.3**, Mininet **2.3.0-1.1**, Open vSwitch **3.3.9-0ubuntu0.24.04.1**. Bản ghi đầy đủ nằm trong `packages.tsv` và `environment.json` của từng lần chạy.

## 2. Cách dựng VM

### Máy của TV1 đã được cấu hình

VM tên `Nhom18-W1`, dùng Ubuntu Cloud Image ARM64 từ Canonical. SHA256 được đối chiếu với bảng checksum tải qua HTTPS; bản ghi nguồn ở [image-source.json](../evidence/week1/image-source.json). Chưa kiểm tra chữ ký GPG của bảng checksum.

Quy trình: nhập QCow2 vào UTM ARM64/UEFI, bật hypervisor, đặt 4 CPU và 4096 MiB RAM, **Resize đĩa lên 32 GiB sau khi import**. Trường Size khi import không thay đổi kích thước image. Khởi tạo bằng cloud-init NoCloud trên ISO nhãn `cidata`, gồm `user-data`, `meta-data` và `network-config`. **Import seed thành ổ VirtIO thứ hai, đặt chỉ đọc**; trong lần dựng này seed gắn kiểu CD USB chưa được cloud-init nhận. Kết quả khởi tạo thành công ghi `DataSourceNoCloud [seed=/dev/vdb]`. Tài khoản guest là `ubuntu`, đăng nhập SSH bằng khóa riêng được giữ cục bộ, tắt đăng nhập SSH bằng mật khẩu và root.

UTM dùng Emulated VLAN/NAT, card `virtio-net-pci`; chuyển tiếp **TCP 127.0.0.1:2222 → guest:22**. Địa chỉ guest của VM này là `10.0.2.15/24`, gateway `10.0.2.2`, DNS `10.0.2.3`. Cloud-init gắn cấu hình mạng theo MAC của NIC; MAC của VM khác phải được lấy từ chính VM đó. Mạng thử Mininet là `10.0.0.0/24`, tách khỏi mạng quản trị VM.

Image, seed ISO và khóa SSH nằm ngoài Git. Trên đúng máy TV1 đã tạo VM:

```bash
ssh -F .local/ssh/config nhom18-w1
```

File `.local/ssh/config` không có trong bản clone; TV2 tạo VM và thông tin đăng nhập của riêng mình.

### TV2 tự dựng một VM

1. Tải Ubuntu Server **24.04** đúng kiến trúc: [ARM64](https://cdimage.ubuntu.com/releases/24.04/release/) cho Apple Silicon; [AMD64](https://releases.ubuntu.com/24.04/) cho Intel/AMD. Đối chiếu SHA256 từ cùng trang phát hành.
2. Trên Mac, tạo VM Linux trong UTM, chọn kiến trúc tương ứng và tăng tốc phần cứng. Trên Windows Intel/AMD, tạo guest Ubuntu 64-bit trong VirtualBox, bật VT-x/AMD-V nếu cần. Đặt tài nguyên theo bảng trên và dùng NAT.
3. Cài Ubuntu vào đĩa ảo của VM; bật OpenSSH nếu cần truy cập từ host. Với UTM Emulated VLAN, có thể thêm chuyển tiếp localhost:2222 → 22; với VirtualBox NAT dùng quy tắc port forwarding tương đương. Cũng có thể thao tác hoàn toàn trong console Ubuntu.
4. Trong guest Ubuntu, chạy các lệnh thiết lập bên dưới. Không chạy script cài đặt trực tiếp trên macOS hoặc Windows.

Nguồn đối chiếu: [UTM hướng dẫn Ubuntu](https://docs.getutm.app/guides/ubuntu/), [UTM cấu hình mạng](https://docs.getutm.app/settings-qemu/devices/network/network/), [VirtualBox: host và guest được hỗ trợ](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/Introduction.html), [Ubuntu Mininet package](https://packages.ubuntu.com/de/noble/mininet), [Ubuntu OVS package](https://packages.ubuntu.com/noble/openvswitch-switch), [Mininet cài đặt và pingall](https://mininet.org/download/), [cloud-init NoCloud](https://docs.cloud-init.io/en/latest/reference/datasources/nocloud.html).

## 3. Cài đặt và kiểm thử trong Ubuntu

```bash
git clone https://github.com/Linhlss/Nhom18_HTMMT.git
cd Nhom18_HTMMT
sudo bash scripts/setup-ubuntu.sh
sudo bash scripts/verify-week1.sh --label tv2-local
```

Script setup dùng APT, không cài Mininet bằng pip. Chạy lại setup sẽ dùng môi trường APT hiện tại và kiểm tra nhánh phiên bản. Ghi lại revision thực tế; không giả định mọi lần cập nhật Ubuntu cho ra cùng số patch.

Script verify dùng **Python hệ thống `/usr/bin/python3`** để thấy module Mininet do APT cài. Không kích hoạt venv cho bài thử này. Workload của TV2 có thể dùng môi trường Python riêng sau khi đặc tả được chốt.

Bài thử tạo `h1=10.0.0.1/24`, `h2=10.0.0.2/24`, OVS bridge `s1`, hai link, không cần OpenFlow controller ngoài. Điều kiện đạt:

- Đúng hai host, một switch, hai link và hai OVS port.
- `pingAll` mất 0%; mỗi chiều gửi 5 gói, nhận đủ 5 gói, lệnh ping trả mã 0.
- Dọn được bridge và các interface của bài thử sau khi chạy.
- Shell trả mã 0; `result.json` có `success: true` và `cleanup_ok: true`.

Log ghi theo UTC trong `evidence/week1/<timestamp>-<label>/`: `run.log`, `result.json`, `environment.json`, `packages.tsv`, `exit-code.txt`. `boot_id` giúp phân biệt các lần khởi động. Đây là log đo trong VM, không phải benchmark Data Center hoặc kết quả hiệu năng AI.

Để kiểm tra cơ chế báo lỗi trên VM riêng, có thể chủ động ngắt link của chính bài thử:

```bash
sudo bash scripts/verify-week1.sh --label negative-control --negative-control
echo "$?"
```

Lần này phải trả mã khác 0 và `success: false`; đây là **lỗi được tạo có chủ đích**, không được tính là kiểm thử kết nối đạt. Script vẫn phải dọn topology. Không chạy bài thử nếu đã có topology khác dùng tên `s1`.

Sau khi khởi động lại VM, chạy lại verify với nhãn `after-reboot`. So sánh `boot_id` và kết quả hai lần để xác minh cấu hình còn hoạt động.

## 4. Xử lý lỗi

| Hiện tượng | Kiểm tra và cách xử lý |
|---|---|
| Script từ chối OS hoặc thiếu quyền | Vào Ubuntu 24.04 VM; chạy bằng `sudo bash`. Script không hỗ trợ cài native macOS/Windows. |
| SSH localhost:2222 không có banner | Kiểm tra VM đang chạy, NIC/port forwarding và console boot; xác nhận cloud-init nhận seed và guest có IP. Không tắt kiểm tra chứng chỉ hay SSH host key để xử lý lỗi mạng. |
| Ubuntu chờ `systemd-networkd-wait-online` | Kiểm tra MAC và tên NIC trong netplan/cloud-init. Với Emulated VLAN của VM TV1, kiểm tra cấu hình 10.0.2.15/24 ở trên. Không dùng nguyên MAC của VM khác. |
| Máy vẫn tên `ubuntu`, không nhận SSH key/cloud-init | Kiểm tra nhãn `cidata`, các file seed và nguồn datasource. Với cloud image này, dùng seed trên VirtIO thay cho CD USB; xem console và `cloud-init status --long`. |
| Đĩa vẫn 3.5 GiB sau import | Khi VM đã dừng, dùng UTM Edit → VirtIO Drive → Resize → 32 GiB; boot và kiểm tra `lsblk`, `df -h /`. |
| Không tìm thấy Mininet | Kiểm tra mạng APT và Ubuntu Universe; chạy lại setup. |
| Không import được `mininet` | Dùng `/usr/bin/python3`, tránh Python trong venv/pip. |
| OVS không hoạt động | Xem `systemctl status openvswitch-switch` và `sudo ovs-vsctl show`; sửa lỗi trước khi chạy lại verify. |
| Đã có `s1` | Dừng đúng topology đang sở hữu tên đó. Không chạy `mn -c` trên testbed đang làm việc để xóa hàng loạt tài nguyên. |
| Test ping thất bại | Đọc cả `run.log` và `result.json`; sửa lỗi rồi chạy lại để tạo log mới. Không sửa log thất bại thành PASS. |
| SSH báo host key thay đổi sau khi dựng lại VM | Xác minh đã tạo lại đúng VM; chỉ cập nhật bản ghi host key của VM đó sau khi đối chiếu, không tắt xác minh SSH toàn cục. |

## 5. Điểm bàn giao TV2 và review TV4

TV2 nhận link repo, tài liệu này, script thiết lập/kiểm thử và các log tuần 1. TV2 tự dựng VM đúng kiến trúc, chạy verify, rồi làm **N18-002**: đặc tả `request_size`, `response_size`, `request_rate`, `concurrency`, `service_delay`, đơn vị và ví dụ cấu hình. Ví dụ đặc tả không được trình bày như dữ liệu đo thực tế. Phần workload/client/server vẫn thuộc TV2.

TV4 kiểm tra các phiên bản, đọc log, chạy lại verify và xác nhận nghiệm thu N18-001. Trạng thái sau khi kiểm thử kỹ thuật đạt là **Chờ kiểm tra**. Chỉ cập nhật **Hoàn thành** và đánh dấu checkbox sau review thật. G1 còn cần đầu ra workload/metrics/scope của TV2–TV4; bài thử hai host không thay thế các đầu ra đó.

Kết quả và các giới hạn kiểm chứng của lần bàn giao được tổng hợp trong [evidence tuần 1](../evidence/week1/README.md).
