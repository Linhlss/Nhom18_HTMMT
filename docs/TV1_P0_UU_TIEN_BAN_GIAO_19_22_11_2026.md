# TV1 — P0: Hoàn tất bàn giao hạ tầng trước để TV2/TV3/TV4 tiếp tục (19–22/11/2026)

> **ĐỌC ĐẦU TIÊN — CLAUDE CODE TRIỂN KHAI, CODEX REVIEW ĐỘC LẬP.** Đây là **danh sách công việc CHƯA NGHIỆM THU**, không phải thông báo đã hoàn thành. TV1 là nhóm trưởng và chủ trì; TV4 kiểm thử chéo. Thời hạn môn học còn 3–5 tuần, ưu tiên một vòng prototype hoạt động hơn tính năng mở rộng.

## 0. Audit những gì ĐÃ CÓ — KHÔNG LÀM LẠI

Trên nhánh main hiện có:
- **topology/model.py**, **topology/runtime.py**, **control/networkctl.py**: mạng 10 node logic (c1,c2,gw,fw,leaf1,leaf2,spine1,spine2,a1,a2), gateway/firewall, cặp preset A/B, API CLI/JSON với start/status/verify/exec/apply/stop.
- **topology/configs/profile_a.json**, **profile_b.json**: A đi Spine 1; B chia luồng tĩnh theo subnet nguồn: c1→Spine 1, c2→Spine 2. **Đây KHÔNG phải ECMP**.
- **scripts/verify-network.py**, **tests/**, **evidence/network/**: minh chứng bộ kiểm thử mạng trên Ubuntu VM TV1. Chẩn đoán iperf3 chưa phải benchmark workload AI inference.
- **workload/** có client/server và bài smoke; **measurement/** có ping/iperf3 probe + converter; **qa/** có checker tuần 1. Không lấy code thuộc TV2/TV3/TV4 làm nhiệm vụ chính của TV1.
- **docs/network-handoff.md**, **docs/env-matrix.md**, **docs/workload-spec.md**, **docs/metrics-spec.md**, **docs/scope-rubric.md** là nguồn tham chiếu.
- PR #4 tuần 1 đã merge main; đừng yêu cầu merge lại.

**Quy tắc:** Trước khi sửa code, đọc các file thực tế trên HEAD mới nhất và chạy unit test. Nếu yêu cầu đã được đáp ứng, **chỉ bổ sung bằng chứng/đối chiếu**, không viết lại một chức năng đã chạy. Nếu HEAD thay đổi trong lúc làm, cập nhật nhánh, không ghi đè work của thành viên khác.

## 1. Thứ tự ưu tiên và người nhận

| Thứ tự | Ưu tiên | DRI | Nội dung | Nhận bàn giao |
|---|---|---|---|---|
| **P0-01** | Làm trước | **TV1 / agent** | Audit + khóa hợp đồng giao diện API, topology, danh sách interface/link/capacity; viết hướng dẫn TV2/TV3 đọc được | TV2, TV3 |
| **P0-02** | Sau P0-01 | **TV1 / agent** | Tạo quy trình kiểm thử bàn giao có thể chạy lại, không phá testbed khác; lưu raw evidence | TV4 và TV2/TV3 |
| **P0-03** | Sau P0-02 | **TV1 chủ trì, TV2/3 thao tác, TV4 review** | Người nhận clone sạch và chạy lại trên VM của mình, ghi phiên bản, lệnh, kết quả | Toàn nhóm |
| **P0-04** | Sau khi TV2 có runner và TV3 có collector | **TV1 + TV2 + TV3, TV4 kiểm chứng** | Pilot A/B cùng workload, chứng minh đường đi thực và so sánh đo | Sản phẩm tích hợp |
| **P0-05** | Xuyên suốt | **TV1 quyết định, TV4 cập nhật** | Chốt SHA bàn giao, theo dõi blocker/issue; chỉ đóng task khi có review | Nhóm trưởng |

**Không** yêu cầu TV1 làm dashboard, workload runner 1/2/4/8 flows, bottleneck detector hoặc recommender — đây là TV2/TV3.

## 2. P0-01 — Khóa hợp đồng tích hợp, làm ngay

### Cách thực hiện

1. Đối chiếu **topology/model.py** (LINKS/ADDRESSES/IPS/ROUTES), **topology/runtime.py** (Network.status), **control/networkctl.py** và **docs/network-handoff.md**. Kiểm tra tài liệu hiện tại có lệch code không.
2. Tạo/cập nhật **docs/network-interface-contract.md** làm tài liệu cho TV2 + TV3; có ví dụ JSON thực **chỉ khi lấy từ log thật**, còn schema minh họa ghi rõ "minh họa". Nêu **các lệnh an toàn** để lấy trạng thái và chạy trong namespace.
3. Bắt buộc có bảng 10 link với hai đầu, tên interface chính xác và capacity: leaf–spine = 25 Mbps, link khác = 100 Mbps (theo cấu hình hiện tại); phải xác minh lại bằng **tc** khi chạy VM. Nêu ingress/egress, hướng nào đọc TX/RX và độ trễ; **không lấy speed 10000 Mbps mà OVS hiển thị làm capacity**.
4. Mô tả hợp đồng **networkctl status** (session_id, profile, config_hash, links, ports, active_commands), exec và apply, mã thoát, trường hợp lỗi, profile chưa xác định, thời gian chờ, cách tránh command injection. Không biến Unix socket local root-only thành HTTP API.
5. **TV2 cần:** c1=10.18.1.10, c2=10.18.2.10, a1=10.18.3.11, a2=10.18.3.12, TCP/8000; khi ≥2 flows cần chia nguồn c1/c2 để B sử dụng 2 spine. **TV3 cần:** inventory interface/link và hướng đo counter; dùng run_id/config_id/profile riêng theo docs/metrics-spec.md và docs/workload-spec.md.
6. Nếu cần xuất inventory máy-đọc-được, ưu tiên **dùng trường links/addresses/ports từ networkctl status hiện có**. Chỉ thêm CLI/export hoặc script read-only khi không thể đáp ứng bằng giao diện hiện có; viết test xác minh dữ liệu đối chiếu model, không hard-code bản thứ hai dễ lệch.

### Nghiệm thu P0-01
- [ ] Có một tài liệu hợp đồng interface với nguồn code rõ ràng, link ID/interfaces, capacity theo chiều.
- [ ] Có lệnh và ví dụ cho TV2 exec workload, TV3 đọc bộ đếm, TV4 verify.
- [ ] Không gọi B là ECMP; không đổi semantics A/B hoặc đổi firewall trong lúc bàn giao.
- [ ] Có unit/static test hoặc script kiểm tra inventory/schema **chạy thật** và log kết quả.
- [ ] TV2 + TV3 xác nhận hiểu schema và có thể bắt đầu phần mình.

## 3. P0-02 — Một quy trình kiểm tra bàn giao tái lập

### Cách thực hiện

1. Xây **scripts/verify-tv1-handoff.sh** (hoặc Python script tiêu chuẩn tương đương) dùng lại script có sẵn, không viết lại phép đo.
2. Có hai chế độ được ghi rõ: **unit/static** (không yêu cầu root/Mininet) và **Ubuntu VM integration** (Ubuntu 24.04, root, Python hệ thống /usr/bin/python3).
3. Trong VM, kiểm tra preflight OS, dependencies; **nếu testbed đã chạy, không tự stop/cleanup tài nguyên không thuộc lượt chạy**. Bộ verify-network.py yêu cầu testbed chưa chạy và tự dựng/dọn; phải tránh gọi khi đang chạy workload.
4. Dùng đúng các lệnh đã tồn tại: python3 -m unittest discover -s tests -v; sudo /usr/bin/python3 scripts/verify-network.py --label ... khi testbed tắt; sau đó networkctl start/status/verify; thử workload/smoke_test.py và measurement/week1_probe.py khi profile A; cuối cùng stop **chỉ nếu script đã tự start**. Cho phép tách các bước nếu tổng thời gian quá lâu.
5. Thử lỗi có chủ đích và rào chắn Apply/Ignore **bằng bộ verify-network.py có sẵn**; giữ audit log. Không tự Apply trong khi workload đang chạy; một thao tác Apply thật ở operator flow chỉ được xác nhận khi được người vận hành đồng ý.
6. Log gốc + exit code + SHA + Ubuntu architecture + package versions + thời gian UTC + command thực chạy được lưu dưới **evidence/tv1-handoff/<UTC>-<label>/** (không ghi đè evidence lịch sử). Script lỗi phải trả nonzero và vẫn dọn tài nguyên do mình tạo; không tráo kết quả thất bại thành PASS.

### Nghiệm thu P0-02
- [ ] Script/hướng dẫn chạy lại dễ làm, phân biệt unit vs VM; không yêu cầu cài thêm cloud/API/GPU.
- [ ] Có test cho nhánh lỗi/đã có testbed; không gọi mn -c bừa bãi.
- [ ] Có log thật đối chiếu mã nguồn, không commit socket, key, ảnh VM hoặc state trong /run.
- [ ] Nếu agent không có Ubuntu VM, đánh dấu **CHƯA XÁC MINH VM**, chỉ báo kết quả test nó thật sự đã chạy.

## 4. P0-03 — Người nhận tự xác minh (không thể đóng bằng code của AI)

1. **TV2:** clone SHA đã chốt trên Ubuntu VM riêng, chạy unit + start/status/verify, sau đó workload smoke, kiểm tra a1/a2/TCP 8000 và c1/c2. Gửi log + SHA + lỗi nếu có.
2. **TV3:** clone cùng SHA, chạy probe của mình, thử đọc link/interface counter thật trên testbed, đối chiếu ít nhất hai link leaf–spine và capacity với tc. Gửi raw + CSV + cách đọc.
3. **TV4:** review log, đối chiếu test và environment, xác nhận hai người không chỉ dùng VM TV1; mở issue cho từng blocker.
4. **TV1:** sửa các lỗi **thuộc phần network/interface** nếu có; không tự kết luận TV2/TV3 đã chạy khi chưa có evidence và review.

**Nghiệm thu:** bảng bàn giao có người chạy, máy/kiến trúc, SHA, lệnh, PASS/FAIL, link evidence, reviewer; sau đó TV4 cập nhật tracker. Việc "agent test pass trên máy TV1" không đủ thay cho bước này.

## 5. P0-04 — Pilot trên cùng offered load (phối hợp sau khi bên nhận sẵn sàng)

- TV2 cung cấp một workload config cố định và runner, tạo lưu lượng từ **cả c1 và c2** khi muốn kiểm tra hai spine; 1 flow từ c1 không thể tự sử dụng Spine 2.
- TV3 cung cấp collector theo từng interface (cửa sổ 1 s, Δt monotonic, counter reset/status đúng), ghép theo run_id/config_id/profile.
- TV1 kiểm chứng A/B bằng port counters/flow dump/PCAP; A qua Spine 1, B phân theo c1/Spine1 và c2/Spine2. **Không** khẳng định automatic load-balancing hoặc self-healing.
- Sau khi workload dừng, operator xác nhận Apply; TV1 áp dụng profile khác, verify, rồi chạy **cùng** workload lần nữa. TV3 kiểm tra RTT/goodput/utilization; TV4 đối chiếu raw.
- Pilot là một vòng demo **chưa thay thế** ma trận chính thức A/B × 1/2/4/8 flows × 3 lần. Tách kết quả iperf3 diagnostic với AI-inference-like workload.

**Nghiệm thu:** một run A và một run B có raw/evidence, đúng forwarding, có biểu đồ/CSV so sánh và limitation. Nếu runner/collector chưa xong thì mở issue/blocker; TV1 không viết thay.

## 6. Thứ tự trong tuần nước rút

- **19/11:** P0-01, khóa interface contract + SHA làm nền, bàn giao ngay cho TV2/TV3 (họ có thể bắt đầu song song).
- **20/11:** P0-02, script/test/hướng dẫn và kết quả agent thực sự chạy. Mốc bàn giao code của TV1.
- **21–22/11:** P0-03 do TV2/TV3 thực hiện trên máy mình, TV4 review; P0-04 một pilot khi có runner/collector.
- Sau 22/11: TV1 chỉ nhận networking bug từ pilot, duyệt gate và hỗ trợ reviewer. TV2 chạy workload + dashboard; TV3 collector/detect/recommend; TV4 QA/báo cáo song song.
- Nếu chỉ còn 3 tuần: bỏ packet animation phức tạp, UI trang trí, ECMP mới, tính năng ngoài P0; hoàn thành Detect→Recommend→Confirm→Apply→Verify→Compare và dữ liệu thật trên VM trước.

## 7. Quy trình hai AI: Claude implementer → Codex reviewer

**Phân công cố định:** Claude Code là tác giả code/test/tài liệu của TV1; Codex là người review độc lập trên PR, **không sửa code, không tự merge**. TV4 QA và TV1 chốt nghiệm thu/merge. Giữ nguyên thứ tự P0-01 (#5) → P0-02 (#6), rồi mới bàn giao P0-03 (#7) và pilot P0-04 (#8).

### Claude Code — triển khai

1. Đọc **CLAUDE.md**, **AGENTS.md**, file này, #5 và các nguồn §0; audit HEAD/kiểm thử hiện tại, tránh viết lại cái đã có.
2. Làm **P0-01** trong branch riêng, tạo PR, đính kèm file sửa, test + log/exit code, file nào chưa thể kiểm tra VM. **Chờ review của Codex**, sửa các phát hiện BLOCKER/MAJOR rồi mới bắt đầu #6 hoặc tách PR rõ ràng.
3. Làm **P0-02** tương tự: tránh stop testbed khác, tái dùng scripts có sẵn, kiểm tra failure case, lưu evidence thật. Đừng sửa module TV2/TV3 vô cớ.
4. Chuẩn bị hướng dẫn để TV2/TV3 tự thực hiện #7, không tự nhận họ đã chạy; #8 chỉ khi workload runner và collector thật sự sẵn sàng.
5. Ghi **docs/ai-prompts-verification-log.md** và tạo PR để review, không tự merge.

### Codex — chỉ review

1. Đọc **AGENTS.md**, file này, Issue liên quan, diff PR của Claude, phần code liên quan và các test/evidence.
2. Kiểm tra chính xác API, mapping node/interface/link, capacity từ tc, OpenFlow path A/B (B **không phải ECMP**), firewall, Apply/Ignore/rollback, active workload guard, tính an toàn cleanup, khả năng TV2/TV3 tích hợp, source/version/log.
3. Chạy các test **nếu môi trường cho phép**; không coi unit test macOS thay thế VM Ubuntu. Nêu rõ cái gì xác minh thật và cái gì chỉ suy luận từ source.
4. Xuất nhận xét theo **BLOCKER/MAJOR/MINOR**, file/dòng và lý do, cách tái hiện/sửa; quyết định **APPROVE / REQUEST CHANGES / NEED VM VERIFICATION**; **không chỉnh code** hoặc tự nhận TV4/TV1 nghiệm thu.
5. Khi Claude sửa, **review lại diff mới**; TV4/TV1 mới chốt.

### Prompt gửi Claude

> Bạn là **IMPLEMENTER**, không phải reviewer. Đọc CLAUDE.md, AGENTS.md và docs/TV1_P0_UU_TIEN_BAN_GIAO_19_22_11_2026.md. Làm Issue #5 (P0-01) trước trên nhánh riêng; dùng lại hạ tầng hiện có; chạy test thực sự khả thi, lưu chứng cứ và tạo PR. Sau khi Codex review, sửa theo feedback rồi mới xử lý Issue #6. Không tự merge, không tự nhận đã được nghiệm thu trên Ubuntu VM nếu chưa chạy.

### Prompt gửi Codex

> Bạn là **REVIEWER ĐỘC LẬP**, không phải người triển khai. Đọc AGENTS.md, kế hoạch TV1, Issue liên quan và PR/diff do Claude Code tạo. Hãy review correctness, topology/port mapping, networkctl API, A/B path, rào chắn Apply/Ignore, cleanup, backward compatibility với TV2/TV3, test/evidence; phân mức BLOCKER/MAJOR/MINOR kèm file/dòng, cách tái hiện và đề xuất sửa. Chạy test chỉ khi thực sự có môi trường. **Không sửa code, không commit, không merge và không tự đánh dấu DONE.** Kết luận APPROVE / REQUEST CHANGES / NEED VM VERIFICATION.

## 8. Phân biệt DONE và TODO

- **Đã làm trên main trước kế hoạch này:** N18-001/005/009/013/017/021/025/029/033/037; tài liệu network handoff; phép đo iperf3 hạ tầng; smoke TV2, probe TV3, checker TV4 tuần 1. Các kết quả đã có phải được kiểm chứng qua evidence đi kèm.
- **Chưa nghiệm thu theo kế hoạch nước rút:** P0-01…P0-04; chỉ chuyển DONE khi đúng các điều kiện nêu trên.
- **Người chịu trách nhiệm cuối:** TV1 duyệt kỹ thuật, TV4 review evidence; TV2/TV3 chịu trách nhiệm tự triển khai và test module của mình.
