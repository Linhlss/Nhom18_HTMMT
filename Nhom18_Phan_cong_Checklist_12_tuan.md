# PHÂN CÔNG & PROGRESS CHECKLIST 12 TUẦN — NHÓM 18 (V2 — NHÓM TRƯỞNG TV1)

**Đề tài:** Nghiên cứu và xây dựng nguyên mẫu (prototype) giám sát, đánh giá cấu hình mạng Data Center Spine–Leaf cho lưu lượng AI Inference  
**Nhân sự:** 4 người (tạm dùng TV1–TV4 vì chưa có tên thành viên). **Nhóm trưởng: TV1.** **Đầu mối điều phối/QA: TV4.**  
**Mốc:** 12 tuần tính từ ngày nhóm bắt đầu triển khai; không gán ngày cố định khi chưa có lịch cụ thể.  
**Trạng thái ban đầu:** Chưa làm. Sau mỗi tuần, nhóm cập nhật tiến độ và gắn bằng chứng; không đánh dấu hoàn thành chỉ dựa trên mô tả hay mã chưa chạy.

## 0. Quyết định tổ chức đã chốt

**TV1 là nhóm trưởng kiêm người phụ trách hạ tầng mạng/Apply.** TV1 chịu trách nhiệm khóa phạm vi, ưu tiên công việc, xử lý phụ thuộc giữa các module và phê duyệt mốc nghiệm thu; đồng thời trực tiếp phát triển topology/routing/profile A–B/Apply. **TV4 làm đầu mối hỗ trợ điều phối, tích hợp và QA:** cập nhật bảng tiến độ, điều phối minh chứng, tập hợp báo cáo và nhắc hạn. TV4 **không** thay TV1 quyết định kỹ thuật mạng, cũng **không** phải viết thay toàn bộ phần của TV1–TV3.

**Không tăng số lượng task P0 chỉ vì đổi nhóm trưởng:** 48 công việc và các mã N18-001...N18-048 giữ nguyên để không làm hỏng tiến độ, phụ thuộc và dashboard; phần quản lý được phân bổ riêng theo bảng bên dưới. Nếu TV1 bị kẹt bởi nhiệm vụ quản lý, ưu tiên chuyển việc ghi chép/chuẩn bị tài liệu cho TV4, không ôm thêm code TV2/TV3.

| Hoạt động quản lý | Quyết định/chịu trách nhiệm | Thực hiện chuẩn bị, cập nhật | Tần suất / bằng chứng |
|---|---|---|---|
| Phân công, ưu tiên và giải quyết blocker | **TV1** | TV4 tập hợp blocker từ TV2–TV3 | Họp 20–30 phút mỗi tuần; biên bản có quyết định/hạn xử lý |
| Theo dõi tracker/nhắc hạn/link evidence | TV1 duyệt tình trạng mốc | **TV4** nhập, chuẩn hóa link, nhắc người nộp | Cập nhật ít nhất 1 lần/tuần; workbook |
| Chốt thiết kế mạng/profile A–B/Apply | **TV1** | TV3 phản biện tiêu chí đo; TV2 kiểm tra API/UI | Commit/config, đường đi và port counters |
| Chốt format workload và metric | TV1 phê duyệt baseline thử nghiệm | **TV2** chịu trách nhiệm workload; **TV3** chịu trách nhiệm metric | `workload-spec.md`, `metrics-spec.md`, phiếu review |
| Kiểm thử tích hợp và QA | TV1 xác nhận gate | **TV4** thiết kế/chạy checklist QA; TV1–TV3 sửa module của mình | `tests/`, issue, biên bản QA |
| Báo cáo 2 chương/slide/demo/tài liệu nộp | **TV1** duyệt bản cuối và nộp chính thức | **TV4** tập hợp, biên tập; TV1–TV3 viết phần chuyên môn của mình | PDF, slide, mã nguồn, evidence manifest |
| Thay đổi phạm vi và ứng phó rủi ro | **TV1** đề xuất phương án, cả nhóm thống nhất | TV4 ghi change log; TV2/TV3 ước lượng ảnh hưởng | Quyết định có lý do, owner và tác động tới deadline |

### Nguyên tắc tránh nhóm trưởng làm thay

- TV1 giúp định hướng và review, **không** tự sửa toàn bộ module của TV2/TV3 nếu họ chưa chứng minh đã debug; task chỉ chuyển owner khi cả nhóm đồng ý và cập nhật tracker.
- TV2 chịu trách nhiệm chạy được client/server + UI; TV3 chịu trách nhiệm metrics/rules/dataset; TV4 chịu trách nhiệm QA/protocol/report; **mỗi người phải demo được phần của mình.**
- Khi một người bị chặn quá **48 giờ**, báo TV1; TV1 xác định người hỗ trợ và mốc giải quyết. TV4 cập nhật issue/tracker; người phụ trách vẫn giữ ownership trừ khi phân công lại.
- **Kiểm tra năng lực tuần 1**: TV1 dựng Mininet 2 host/ping; TV2 chạy Python request/response; TV3 xuất CSV từ kết quả `ping`/`iperf3`; TV4 chạy packet capture hoặc kiểm tra log, tạo issue và biên bản. Đây là bài thử khởi động, không tuyên bố là task P0 đã hoàn thành.

## 1. Quy tắc quản lý

- **Một task chỉ có 1 người chịu trách nhiệm chính (DRI)**, nhưng phải có người khác kiểm thử. Người phụ trách không đồng nghĩa làm một mình.
- Định nghĩa **Hoàn thành:** có file/commit/ảnh/log theo cột “Bằng chứng”; một người khác đã kiểm tra; thỏa điều kiện nghiệm thu. Task đang code nhưng chưa chứng minh được để “Đang làm”.
- Trạng thái áp dụng: `Chưa làm`, `Đang làm`, `Chờ kiểm tra`, `Hoàn thành`, `Bị chặn`.
- Ưu tiên: **P0 bắt buộc trước**, **P1 mở rộng chỉ làm khi P0 và E01–E10 đạt**.
- **TV1 chủ trì** cuộc họp 20–30 phút mỗi tuần: quyết định ưu tiên/blockers/gate. **TV4** ghi biên bản và cập nhật tổng hợp trong `.xlsx`.
- Quy tắc thay đổi phạm vi: không thêm RL/AI routing, production self-healing, GPU thật, Kubernetes hoặc cấu hình thiết bị thật; mọi đề xuất mới phải gắn chi phí và đổi ưu tiên, được cả nhóm chấp thuận.
- Khi test bằng AI hỗ trợ code: **AI Prompts & Verification Log** là một đầu ra báo cáo có điều kiện bắt buộc; lưu prompt + lỗi + cách kiểm chứng + commit sửa.

## 2. Phân công 4 thành viên

| Thành viên | Vai trò chính | Cụ thể chịu trách nhiệm | Người kiểm thử chéo |
|---|---|---|---|
| **TV1 — Nhóm trưởng / Network Lead** | Hạ tầng mạng, Apply và ra quyết định | Mininet/OVS; routing/firewall; profile A/B; Apply thật; chốt thiết kế, ưu tiên, mốc và xử lý blocker. **Không ôm báo cáo/ghi tracker hằng ngày.** | TV4 (mạng/QA), TV3 (metric) |
| **TV2 — Workload / UI Lead** | Workload và giao diện | Python request/response; concurrent flows; runner; dashboard; kết nối thao tác Apply với TV1; tài liệu module | TV3 |
| **TV3 — Monitoring / Analysis Lead** | Đo lường, phát hiện nghẽn, khuyến nghị | Counter/RTT/throughput; rule bottleneck, alert/recommend, thống kê A/B; viết phần kết quả | TV1 |
| **TV4 — Integration / QA & PM Support** | Tích hợp, QA, tài liệu và hỗ trợ quản lý | Protocol/packet capture; smoke/E2E test; biên tập báo cáo; **nhắc tiến độ, cập nhật tracker, ghi biên bản, tổng hợp minh chứng** | TV2 (app), TV1 (nghiệm thu) |

**Cân bằng kỹ thuật:** mỗi thành viên giữ **12 task P0** trải đều 12 tuần, cùng khung điểm 51; còn **1 task P1** (2 điểm) nếu còn thời gian. TV1 nhận thêm vai trò quyết định/điều phối, còn TV4 tiếp nhận phần hành chính và cập nhật tiến độ để tránh TV1 quá tải. Đây là **ước lượng phân công ban đầu**, cần điều chỉnh nếu máy/khả năng khác nhau; tổng số task không phản ánh chính xác độ nặng của công việc nếu không có evidence và review chéo.

**Phần cần làm chung:** chọn profile A/B khả thi; khóa workload/thresholds sau pilot; duyệt mỗi milestone; chạy demo và phản biện chéo. TV4 không phải người viết báo cáo thay cả nhóm: TV1–TV3 phải cung cấp code, bảng, hình, kết quả và phần giải thích của mình. TV1 là người duyệt bản cuối.

## 3. Gates/đường găng không được trễ

| Gate | Cuối tuần | Điều kiện chốt | Nếu không đạt |
|---|---:|---|---|
| G1 — Scope + môi trường | W1 | Có đặc tả workload/metric, Ubuntu VM khả thi, RQ/ru-bic chốt | Không tăng tính năng; sửa environment sớm |
| G2 — Fabric hoạt động | W3 | 10 node chạy, routing/gateway/firewall hợp lệ, packet trace có | Tạm dừng dashboard, sửa đường mạng |
| G3 — Benchmark end-to-end | W4 | Client–server tạo request, đo RTT/throughput ra raw log | Không triển khai Recommend cho đến khi có dữ liệu tin cậy |
| G4 — Profile A/B được kiểm chứng | W6 | Có 2 profile, path counters chứng minh khác biệt; detection pilot | Không gọi ECMP nếu không phải ECMP |
| G5 — Vòng thao tác đầy đủ | W9 | Detect → Recommend → Confirm → Apply → Verify → Compare chạy thực | Giảm trang trí UI, ưu tiên flow hoạt động |
| G6 — Dữ liệu cuối | W10 | A/B×4 tải×3 lần, raw+summary+evidence đủ | Không dựng số liệu; giảm P1 nếu cần |
| G7 — Handoff | W12 | Báo cáo 2 chương, README, demo, evidence + kiểm tra chéo | Chỉ nộp những tính năng đã chạy và đã chứng minh |

### Cách TV1 điều phối từng giai đoạn mà không gánh thay người khác

| Giai đoạn | TV1 phải chốt | TV4 hỗ trợ/ghi nhận | Tài liệu cần có |
|---|---|---|---|
| W1–W3 | Chạy network, phân vai, scope và chuẩn VM | Theo dõi bài thử năng lực, tracker và kiểm thử kết nối | env-matrix, issue board, bằng chứng G2 |
| W4–W6 | Profile A/B, tính đúng forwarding, giới hạn scope | Soát log baseline, QA/gate G3–G4 | profile A/B, raw log, biên bản kiểm chứng |
| W7–W9 | Kiểm soát Apply/Ignore, phê duyệt gate end-to-end | QA UI/E2E, xác nhận hành vi và ghi blocker | video demo, test cases, bugs đã xử lý |
| W10–W12 | Khóa release, chốt kết luận và duyệt báo cáo | Thu evidence, tổng hợp báo cáo, chuẩn bị demo | dataset, biểu đồ, báo cáo và manifest |

## 4. Bảng checklist đầu việc (52 task, trong đó 48 P0)

### Tuần 01

- [ ] **N18-001 | TV1 | 2 điểm — Chuẩn hóa kiến trúc VM Ubuntu & tài liệu cài đặt**  
  - Nghiệm thu: Bảng version OS/Mininet/OVS; xác minh Windows/macOS có phương án VM phù hợp  
  - Phụ thuộc: —  
  - Minh chứng: `docs/env-matrix.md`
- [ ] **N18-002 | TV2 | 2 điểm — Đặc tả workload request/response và cấu hình**  
  - Nghiệm thu: Chốt trường size/rate/concurrency/service-delay; schema có ví dụ không dùng như dữ liệu đo  
  - Phụ thuộc: —  
  - Minh chứng: `docs/workload-spec.md`
- [ ] **N18-003 | TV3 | 2 điểm — Đặc tả metrics, baseline và protocol đo**  
  - Nghiệm thu: Bảng metric có đơn vị, công thức và công cụ; kế hoạch đo RTT/throughput/utilization  
  - Phụ thuộc: —  
  - Minh chứng: `docs/metrics-spec.md`
- [ ] **N18-004 | TV4 | 2 điểm — Soạn RQ, phạm vi, rubric và cấu trúc repository để TV1 phê duyệt**  
  - Nghiệm thu: RQ1-3 + E01-E10 + tài liệu 2 chương và conventions; issue board; TV1 xác nhận phạm vi  
  - Phụ thuộc: —  
  - Minh chứng: `docs/scope-rubric.md`

### Tuần 02

- [ ] **N18-005 | TV1 | 4 điểm — Dựng Mininet topology sơ bộ 2×2 và host**  
  - Nghiệm thu: Mạng tạo/xóa ổn định; `nodes`,`net`,`links` ghi log  
  - Phụ thuộc: N18-001  
  - Minh chứng: `topology/topology.py; evidence/w2_network.txt`
- [ ] **N18-006 | TV2 | 4 điểm — Client/server Python cơ bản**  
  - Nghiệm thu: Một request/response thành công, log timestamp và payload size  
  - Phụ thuộc: N18-002  
  - Minh chứng: `workload/client.py; workload/server.py`
- [ ] **N18-007 | TV3 | 4 điểm — Kịch bản đo ping/iperf3 baseline**  
  - Nghiệm thu: Chạy thử lưu RTT và throughput raw có timestamp  
  - Phụ thuộc: N18-003  
  - Minh chứng: `measurement/baseline.py; results/raw/`
- [ ] **N18-008 | TV4 | 4 điểm — Sơ đồ OSI/TCP-IP và kế hoạch packet capture**  
  - Nghiệm thu: Protocol stack tách network path; check-list ARP/TCP/HTTP/ICMP  
  - Phụ thuộc: N18-004  
  - Minh chứng: `docs/packet-flow.md`

### Tuần 03

- [ ] **N18-009 | TV1 | 4 điểm — Hoàn thiện routing/gateway/firewall và kiểm tra đường đi**  
  - Nghiệm thu: Client↔server thông; không loop; gateway/firewall không bottleneck ở tải chính  
  - Phụ thuộc: N18-005  
  - Minh chứng: `topology/configs/; evidence/w3_routes.txt`
- [ ] **N18-010 | TV2 | 4 điểm — Hỗ trợ 1/2/4/8 concurrent flows**  
  - Nghiệm thu: 2 client logic tạo đủ 8 flow; ghi số request, status và duration  
  - Phụ thuộc: N18-006  
  - Minh chứng: `workload/runner.py; tests/test_concurrency.py`
- [ ] **N18-011 | TV3 | 4 điểm — Thu counter riêng từng link và time window**  
  - Nghiệm thu: Đọc byte/packet counter có timestamp; kiểm chứng một link có số byte tăng  
  - Phụ thuộc: N18-007  
  - Minh chứng: `measurement/collect_ports.py`
- [ ] **N18-012 | TV4 | 4 điểm — Capture packet và rà giao thức end-to-end**  
  - Nghiệm thu: Có pcap và mô tả encapsulation/forwarding; dữ liệu mô phỏng ghi đúng nhãn  
  - Phụ thuộc: N18-008  
  - Minh chứng: `evidence/w3_packet.pcap; docs/protocol.md`

### Tuần 04

- [ ] **N18-013 | TV1 | 5 điểm — Khóa profile A single-path có thể tái lập**  
  - Nghiệm thu: Traffic đi đúng spine đã định; xuất cấu hình đường đi có version  
  - Phụ thuộc: N18-009  
  - Minh chứng: `topology/configs/profile_a.yaml`
- [ ] **N18-014 | TV2 | 5 điểm — Workload HTTP/TCP chuẩn hóa request/response**  
  - Nghiệm thu: Log request/response cùng ID; size/rate/service-time thực thi đúng config  
  - Phụ thuộc: N18-010  
  - Minh chứng: `workload/; tests/test_payload.py`
- [ ] **N18-015 | TV3 | 5 điểm — Tích hợp đo baseline RTT/throughput từ workload**  
  - Nghiệm thu: Chạy một testcase end-to-end; có raw CSV hợp lệ, không nhập tay  
  - Phụ thuộc: N18-011  
  - Minh chứng: `measurement/; results/raw/pilot.csv`
- [ ] **N18-016 | TV4 | 5 điểm — Smoke test và CI hoặc script QA cơ bản**  
  - Nghiệm thu: Một lệnh chạy test; fail có log; cập nhật issue bug  
  - Phụ thuộc: N18-012  
  - Minh chứng: `tests/smoke.sh; evidence/w4_smoke.txt`

### Tuần 05

- [ ] **N18-017 | TV1 | 5 điểm — Dựng profile B hai đường có kiểm chứng**  
  - Nghiệm thu: Chứng minh flow đi qua 2 spine; ghi đúng flow-splitting hay ECMP theo cơ chế thực tế  
  - Phụ thuộc: N18-013  
  - Minh chứng: `topology/configs/profile_b.yaml; evidence/w5_paths.txt`
- [ ] **N18-018 | TV2 | 5 điểm — Ổn định workload profile và điều kiện xử lý giả lập**  
  - Nghiệm thu: Duy trì offered load, không nhầm server time với RTT; log per flow  
  - Phụ thuộc: N18-014  
  - Minh chứng: `workload/config.yaml; evidence/w5_workload.csv`
- [ ] **N18-019 | TV3 | 5 điểm — Hoàn thiện link utilization sampler**  
  - Nghiệm thu: Utilization tính từ delta counters/interval/capacity; nêu sai số  
  - Phụ thuộc: N18-015  
  - Minh chứng: `measurement/link_util.py; results/raw/`
- [ ] **N18-020 | TV4 | 5 điểm — Kế hoạch thí nghiệm đối chứng và 3 lần lặp**  
  - Nghiệm thu: Bảng A/B×1/2/4/8; warm-up/duration/seed/precondition chốt  
  - Phụ thuộc: N18-016  
  - Minh chứng: `docs/experiment-plan.md`

### Tuần 06

- [ ] **N18-021 | TV1 | 5 điểm — API/script chuyển profile A↔B an toàn**  
  - Nghiệm thu: Cấu hình idempotent; log trước/sau; kiểm tra đường đi sau khi chuyển  
  - Phụ thuộc: N18-017  
  - Minh chứng: `control/apply_profile.py`
- [ ] **N18-022 | TV2 | 5 điểm — Experiment runner chạy lô theo matrix**  
  - Nghiệm thu: Một lệnh chạy 1/2/4/8 và ghi run_id/config_id  
  - Phụ thuộc: N18-018  
  - Minh chứng: `experiments/run_matrix.py`
- [ ] **N18-023 | TV3 | 5 điểm — Luật phát hiện bottleneck dựa nhiều metric**  
  - Nghiệm thu: Áp dụng utilization kéo dài + RTT/throughput; test false positive & true positive  
  - Phụ thuộc: N18-019  
  - Minh chứng: `monitoring/detect.py; tests/test_detection.py`
- [ ] **N18-024 | TV4 | 5 điểm — QA baseline/telemetry và kiểm chứng capture**  
  - Nghiệm thu: So sánh counter với ping/iperf/pcap; ghi khác biệt; phát hiện lỗi thiết kế  
  - Phụ thuộc: N18-020  
  - Minh chứng: `tests/test_telemetry.py; qa/w6.md`

### Tuần 07

- [ ] **N18-025 | TV1 | 5 điểm — Rào chắn Apply/Ignore và xử lý lỗi áp dụng**  
  - Nghiệm thu: Không có thay đổi khi Ignore; Apply chỉ profile hợp lệ và log đầy đủ  
  - Phụ thuộc: N18-021  
  - Minh chứng: `control/approval.py; tests/test_apply.py`
- [ ] **N18-026 | TV2 | 5 điểm — Dashboard tối thiểu cho run, metrics và alert**  
  - Nghiệm thu: Chọn run/profile; xem metric, alert; không cần hệ thống quản trị đầy đủ  
  - Phụ thuộc: N18-022  
  - Minh chứng: `ui/; evidence/w7_ui.png`
- [ ] **N18-027 | TV3 | 5 điểm — Alert và baseline threshold calibration**  
  - Nghiệm thu: Báo warning rõ link và lý do; threshold cố định sau pilot  
  - Phụ thuộc: N18-023  
  - Minh chứng: `monitoring/alerts.py; docs/thresholds.md`
- [ ] **N18-028 | TV4 | 5 điểm — QA hành trình UI, failure và kiểm thử bỏ qua**  
  - Nghiệm thu: Các ca error/ignore không thay đổi mạng; bug log được triage  
  - Phụ thuộc: N18-024  
  - Minh chứng: `tests/test_ui_flow.py; qa/w7.md`

### Tuần 08

- [ ] **N18-029 | TV1 | 5 điểm — Apply profile B thực lên OVS khi xác nhận**  
  - Nghiệm thu: Nhấn Apply tác động đúng flow/routing testbed; counter/path đổi; có log  
  - Phụ thuộc: N18-025  
  - Minh chứng: `control/; evidence/w8_apply.txt`
- [ ] **N18-030 | TV2 | 5 điểm — UI Verify và bảng Compare sơ bộ**  
  - Nghiệm thu: Chọn A/B, thấy status Apply và 2 lần run, có bảng trước/sau  
  - Phụ thuộc: N18-026  
  - Minh chứng: `ui/compare.py; evidence/w8_compare.png`
- [ ] **N18-031 | TV3 | 5 điểm — Rule khuyến nghị có giải thích và ràng buộc**  
  - Nghiệm thu: Nếu 1 link bão hòa và path còn dư → thử B; nếu cả hai bão hòa → không hứa B hiệu quả  
  - Phụ thuộc: N18-027  
  - Minh chứng: `monitoring/recommend.py; tests/test_rules.py`
- [ ] **N18-032 | TV4 | 5 điểm — Bản thảo phần 2.2–2.3 và kiểm chứng flow diagram**  
  - Nghiệm thu: Yêu cầu, I/O, topology, module, sơ đồ protocol và Apply rõ; trích dẫn hợp lý  
  - Phụ thuộc: N18-028  
  - Minh chứng: `report/chap2_design.md`

### Tuần 09

- [ ] **N18-033 | TV1 | 5 điểm — Hoàn thiện kiểm chứng A/B và xử lý bất nhất đường đi**  
  - Nghiệm thu: Có bằng chứng counter/path cho từng profile; fix loop/routing mismatch  
  - Phụ thuộc: N18-029  
  - Minh chứng: `evidence/w9_pathcheck.txt`
- [ ] **N18-034 | TV2 | 5 điểm — Tích hợp end-to-end một vòng operator**  
  - Nghiệm thu: Run → Detect → Recommend → Confirm → Apply → Verify → Compare hoạt động  
  - Phụ thuộc: N18-030  
  - Minh chứng: `tests/e2e.sh; evidence/w9_demo.mp4`
- [ ] **N18-035 | TV3 | 5 điểm — Module so sánh A/B cùng offered load**  
  - Nghiệm thu: Tính % delta RTT/throughput; cờ điều kiện không tương đương  
  - Phụ thuộc: N18-031  
  - Minh chứng: `analysis/compare.py; tests/test_compare.py`
- [ ] **N18-036 | TV4 | 5 điểm — Kiểm thử tích hợp và đánh giá UX tối thiểu**  
  - Nghiệm thu: Test toàn vòng, test không nghẽn/không khuyến nghị; có biên bản QA  
  - Phụ thuộc: N18-032  
  - Minh chứng: `qa/w9_integration.md`

### Tuần 10

- [ ] **N18-037 | TV1 | 4 điểm — Ổn định topology/config và kiểm tra bottleneck biên**  
  - Nghiệm thu: Gateway/firewall không nghẽn ngoài ý muốn; chốt version cấu hình  
  - Phụ thuộc: N18-033  
  - Minh chứng: `topology/; evidence/w10_linkcheck.txt`
- [ ] **N18-038 | TV2 | 4 điểm — Chạy full matrix tạo raw logs có version**  
  - Nghiệm thu: Tối thiểu A/B×4 tải×3 lần; raw data với timestamp/run_id  
  - Phụ thuộc: N18-034  
  - Minh chứng: `results/raw/`
- [ ] **N18-039 | TV3 | 4 điểm — Xử lý metric, thống kê trung bình/độ dao động**  
  - Nghiệm thu: Làm sạch dữ liệu theo rule có ghi; không sửa tay; bảng/biểu đồ thực  
  - Phụ thuộc: N18-035  
  - Minh chứng: `analysis/; results/summary.csv`
- [ ] **N18-040 | TV4 | 4 điểm — Audit dữ liệu và tiêu chí E01–E10**  
  - Nghiệm thu: Đủ evidence cho từng gate; truy xuất từ chart về raw run  
  - Phụ thuộc: N18-036  
  - Minh chứng: `qa/evidence-audit.md`

### Tuần 11

- [ ] **N18-041 | TV1 | 4 điểm — Script setup sạch và hướng dẫn mạng/routing**  
  - Nghiệm thu: Cài mới trên VM chuẩn có checklist chạy; không cần thao tác thủ công mơ hồ  
  - Phụ thuộc: N18-037  
  - Minh chứng: `setup/; README.md`
- [ ] **N18-042 | TV2 | 4 điểm — Ổn định dashboard và chuẩn bị kịch bản demo**  
  - Nghiệm thu: Trạng thái metrics/alert/apply/compare xem được; demo script rõ  
  - Phụ thuộc: N18-038  
  - Minh chứng: `ui/; docs/demo-script.md`
- [ ] **N18-043 | TV3 | 4 điểm — Hoàn thiện biểu đồ và trả lời RQ1–RQ3**  
  - Nghiệm thu: Có bảng biểu và phân tích không suy rộng; số liệu chính có nguồn  
  - Phụ thuộc: N18-039  
  - Minh chứng: `results/figures/; report/results.md`
- [ ] **N18-044 | TV4 | 4 điểm — Soạn báo cáo hai chương và tài liệu tham khảo**  
  - Nghiệm thu: Đúng 1.1–1.5/2.1–2.5, OSI/metrics/AI component, AI usage log nếu có  
  - Phụ thuộc: N18-040  
  - Minh chứng: `report/report.tex; report/references.bib`

### Tuần 12

- [ ] **N18-045 | TV1 | 3 điểm — Thử từ môi trường sạch trên máy thành viên khác**  
  - Nghiệm thu: Script cài/chạy kiểm chứng được, ghi phiên bản VM và lỗi còn lại  
  - Phụ thuộc: N18-041  
  - Minh chứng: `qa/reproducibility.md`
- [ ] **N18-046 | TV2 | 3 điểm — Đóng gói bản chạy, demo và hướng dẫn operator**  
  - Nghiệm thu: Demo end-to-end chạy ổn; README bước Apply/Ignore minh bạch  
  - Phụ thuộc: N18-042  
  - Minh chứng: `release/; docs/operator-guide.md`
- [ ] **N18-047 | TV3 | 3 điểm — Soát số liệu cuối, giới hạn & kết luận**  
  - Nghiệm thu: Các bảng đúng công thức, không báo cải thiện khi không có bằng chứng  
  - Phụ thuộc: N18-043  
  - Minh chứng: `qa/final-metrics.md`
- [ ] **N18-048 | TV4 | 3 điểm — Phản biện chéo, chuẩn bị slide, báo cáo và bộ hồ sơ để TV1 duyệt/nộp**  
  - Nghiệm thu: 4 người giải thích được toàn hệ thống; bộ báo cáo/slide + evidence manifest được TV1 duyệt trước khi nộp  
  - Phụ thuộc: N18-044  
  - Minh chứng: `report/final.pdf; slides/; evidence/manifest.csv`

### P1 — tùy chọn, không tính trong tiến độ P0

- [ ] **N18-049 | TV1** — Mở rộng testcase thay bandwidth riêng; nghiệm thu: Có testcase riêng, không gộp kết quả thay bandwidth với so sánh A/B (bằng chứng: `experiments/optional_capacity.yaml`).
- [ ] **N18-050 | TV2** — Nâng UI thành realtime chart phong phú; nghiệm thu: Không ảnh hưởng độ ổn định core; công cụ vẫn chạy khi không có UI (bằng chứng: `ui/optional_realtime.py`).
- [ ] **N18-051 | TV3** — Xuất báo cáo PDF tự động; nghiệm thu: PDF chỉ tổng hợp dữ liệu thật đã đo, không dựng giá trị (bằng chứng: `analysis/export_report.py`).
- [ ] **N18-052 | TV4** — Thử topo lớn hơn 4 leaf/8 hosts; nghiệm thu: Chỉ làm sau core và ghi giới hạn tài nguyên VM (bằng chứng: `experiments/optional_scale.md`).

## 5. Mẫu cập nhật mỗi tuần (TV4 chuẩn bị; TV1 duyệt quyết định)

```text
Tuần W__ / ngày:
Người phụ trách:
Task đã hoàn thành (kèm commit/ảnh/log):
Task đang làm + % chưa được phép tính “done”:
Task bị chặn / nguyên nhân / người hỗ trợ / hạn xử lý:
Quyết định đổi phạm vi hoặc thay đổi cấu hình (TV1 duyệt):
Kế hoạch tuần tiếp theo:
Bằng chứng đã review chéo bởi:
TV1 đã duyệt gate/mốc (Có/Không):
```

## 6. Checklist nghiệm thu cuối và bảo vệ

- [ ] Chương 1 gồm 1.1–1.5, nguồn tham khảo có xuất xứ, giải thích rõ Spine–Leaf/AI workload/bottleneck/monitoring/Mininet.
- [ ] Chương 2 gồm 2.1–2.5, có vấn đề, RQ, I/O, kiến trúc, giao thức, thực nghiệm, kết luận.
- [ ] Có 10 node logic và chứng minh đường đi từ C1/C2 tới A1/A2.
- [ ] Profile A/B đổi đường đi thật trong testbed; bằng chứng path/counter.
- [ ] Workload request/response 1/2/4/8 flow được log và phân biệt với LLM thật.
- [ ] RTT/throughput/utilization/bottleneck có raw logs; d_trans được tính rõ L/R.
- [ ] Detect dựa trên nhiều dấu hiệu, có test tải thấp và test gây bão hòa.
- [ ] Recommend đưa lý do và không hứa sẽ cải thiện nếu chưa Verify.
- [ ] Ignore không đổi mạng; Apply yêu cầu xác nhận và đổi cấu hình testbed thật.
- [ ] Before/after so sánh cùng offered load, có tối thiểu 3 lần chạy mỗi testcase.
- [ ] Báo cáo nêu rõ giới hạn mô phỏng trên VM; không suy ra hiệu quả trên Data Center thật.
- [ ] Có README, cấu hình environment, demo script, slide, evidence và AI log nếu có dùng AI hỗ trợ code.

## 7. Mô tả trạng thái dự án hiện tại

Bản đề cương và checklist này được lập làm **kế hoạch triển khai**, với TV1 là nhóm trưởng và TV4 làm đầu mối tổng hợp tiến độ/QA. Chưa có bằng chứng nhóm đã code, kiểm thử, thu số liệu hay hoàn thành bất kỳ task kỹ thuật nào. Vì vậy tất cả task trong bảng tiến độ khởi tạo `Chưa làm` cho tới khi từng thành viên cập nhật bằng chứng.
