# Phạm vi, câu hỏi nghiên cứu, rubric nghiệm thu và quy ước dự án (N18-004)

| Mục | Nội dung |
|---|---|
| Task | **N18-004**, tuần 1 — Soạn RQ, phạm vi, rubric và cấu trúc repository để TV1 phê duyệt |
| Người phụ trách (DRI) | TV4 |
| Người review | TV2 (tính rõ ràng, khả năng kiểm thử) |
| Phê duyệt | **TV1** (phạm vi và rubric) |
| Phiên bản | **v1.0**, 18/11/2026. Thay bản nháp v0 `Tiến_độ_final_hệ_thống_mạng.pdf` (ngoài repo); thay đổi ở [§9](#9-thay-đổi-so-với-bản-nháp-v0) |
| Trạng thái | **Chờ kiểm tra** — chờ TV2 review và TV1 phê duyệt |
| Nguồn gốc | [Đề cương chi tiết](../Nhom18_De_cuong_chi_tiet.md) (source of truth), [Phân công 12 tuần](../Nhom18_Phan_cong_Checklist_12_tuan.md) |

## 1. Bối cảnh minh họa — **giả định**

> Mọi chi tiết trong mục này là **tình huống giả định** để giải thích bài toán. Nhóm **không** khảo sát ngân hàng nào, **không** có dữ liệu nội bộ; các con số (số nhân viên, khung giờ, mức dùng GPU) là **giả định minh họa**, không phải số liệu đo hay trích dẫn.

Giả định một ngân hàng (gọi là “Ngân hàng X”, giả định khoảng 3.000 nhân viên) đưa vào dùng trợ lý AI nội bộ để tra cứu quy trình. Giai đoạn thử nghiệm ít người dùng thì phản hồi nhanh. Khi mở rộng, giả định đầu giờ sáng nhiều người hỏi cùng lúc, chatbot chậm và báo timeout. Bộ phận AI Platform thấy GPU chỉ dùng khoảng 40 % (**giả định**) nên cho rằng do mạng; Network Operations thấy ping bình thường, utilization trung bình thấp nên cho rằng do ứng dụng. Mỗi bên đúng ở góc nhìn của mình nhưng không ai chỉ ra được link nào nghẽn và nên đổi gì.

Đặc điểm kỹ thuật làm bài toán xuất hiện (kiến thức chung, cần trích dẫn nguồn ở Chương 1): lưu lượng east–west; inference là request/response độc lập, khác đồng bộ gradient khi huấn luyện; response thường lớn hơn request; nhiều luồng chung link/hàng đợi làm tăng RTT, gây mất gói; cân bằng theo hash (ECMP) có thể lệch; oversubscription làm uplink thành điểm nghẽn.

**Vấn đề cần giải quyết:** thiếu một môi trường kiểm thử **tái lập được**, sinh tải giống AI inference có tham số, chỉ ra điểm nghẽn bằng nhiều tín hiệu, cho phép thử cấu hình **an toàn** với xác nhận của người vận hành và chứng minh bằng số liệu trước–sau.

## 2. Câu hỏi nghiên cứu (giữ nguyên theo đề cương A.2)

**RQ chính:** Với workload AI inference được xác định và kiểm soát, kiến trúc Spine–Leaf có hiệu năng như thế nào dưới các mức tải khác nhau, và việc thử cấu hình khác có cải thiện được các chỉ số mạng hay không?

- **RQ1 — Tải và hiệu năng:** khi tăng số luồng đồng thời 1/2/4/8, RTT và throughput (tổng/từng luồng) thay đổi ra sao? Mức tải nào bắt đầu có dấu hiệu bão hòa trong **môi trường mô phỏng đã cấu hình**?
- **RQ2 — Chẩn đoán:** dùng link utilization kết hợp throughput và RTT có xác định đúng link chịu tải tới hạn không? Bằng chứng kiểm chứng đường đi và counter là gì?
- **RQ3 — Lựa chọn cấu hình:** với cùng workload và điều kiện đo, cấu hình A (single-path) và B (flow-splitting tĩnh qua hai spine; chỉ gọi ECMP nếu hiện thực và chứng minh đúng cơ chế) khác nhau như thế nào? Sau khi người vận hành chọn Apply, kết quả có được ghi nhận và so sánh lại đúng cách không?

**Giả thuyết cần kiểm chứng, không phải kết luận có sẵn:** ở cấu hình chia tải hợp lệ, link quá tải có thể giảm tải nếu đường còn lại thực sự còn dung lượng; hiệu quả không mặc định luôn tích cực.

Định nghĩa “RTT”, “throughput”, “utilization” trong các RQ theo [metrics-spec.md](metrics-spec.md): báo cáo phải nói rõ đang dùng `icmp_rtt_ms`, `app_response_ms` hay `network_residual_est_ms`, và goodput hay throughput interface.

## 3. Phạm vi

### 3.1. Trong phạm vi (P0)

| Hạng mục | Chốt | Nguồn đặc tả |
|---|---|---|
| Testbed | Mininet/OVS trong Ubuntu 24.04 VM; **10 node logic** = 2 client + 2 AI server emulator + 2 leaf + 2 spine + gateway + firewall | [network-handoff.md](network-handoff.md) |
| Profile | A single-path qua Spine 1; B static OpenFlow flow-splitting theo subnet client (**không phải ECMP**) | network-handoff §3 |
| Workload | Request/response **giả lập**, `tcp-binary-v1` TCP/8000; 1/2/4/8 flow từ 2 client logic; không LLM/GPU | [workload-spec.md](workload-spec.md) |
| Metric | RTT ICMP, thời gian ứng dụng tách server/residual, goodput vs throughput interface, utilization từng chiều, drop/loss | [metrics-spec.md](metrics-spec.md) |
| Vòng thao tác | Tạo tải → Monitor → Detect → Recommend → **operator xác nhận** → Apply trên testbed → Verify → Compare | Đề cương A.3 |
| Apply | Chỉ preset A/B đã kiểm thử; cần `--confirm`; Ignore không đổi gì; log old/new | network-handoff §5 |
| Đánh giá | A/B × 1/2/4/8 flow × ≥ 3 lần, cùng offered load | Đề cương 2.4 |

### 3.2. P1 (chỉ khi P0 và E01–E10 đã đạt)

Thử capacity link riêng; mở rộng node/flow; biểu đồ realtime; xuất PDF tự động; HTTP workload.

### 3.3. Ngoài phạm vi

GPU/LLM thật, training/NCCL/RDMA, Kubernetes/cloud, AI-based routing, anomaly detection/ML dự đoán, **self-healing/tự chuyển tuyến**, cấu hình thiết bị/mạng production, khảo sát dữ liệu doanh nghiệp. Kết luận chỉ áp dụng cho testbed đã cấu hình.

Thay đổi phạm vi theo đề cương C.2: `yêu cầu → lý do → ảnh hưởng tuần/người → có cắt P0 không → quyết định`; TV4 ghi change log, **TV1 quyết định**.

## 4. Rubric nghiệm thu E01–E10 (cho cả dự án)

Rubric áp dụng toàn dự án; **không** yêu cầu đạt hết ở tuần 1. Chủ trì và người review khớp sheet `Nghiệm thu` của tracker. Trạng thái dưới đây là trạng thái **thực tế** ngày 18/11/2026.

| Mã | Tiêu chí | Chủ trì | Bằng chứng bắt buộc | Review | Điều kiện đạt | Mốc | Trạng thái |
|---|---|---|---|---|---|---|---|
| **E01** | Topology 10 node, routing đúng; gateway/firewall không nghẽn ngoài ý muốn | TV1 | `topology/`, `network-state.json`, `tc.json`, ping 8 hướng, kết quả verify | TV4 | Đủ 10 node/10 link; rate từng interface đúng; 8 hướng client↔server 0 % loss; firewall chỉ mở 8000, 5201–5208 | G2/W3 | Chờ kiểm tra |
| **E02** | Profile A/B đi khác nhau, có counter/trace | TV1 | PCAP + delta counter từng spine cho A và B, ≥ 3 lượt mỗi profile | TV4 | A: chỉ Spine 1 có lưu lượng; B: c1 qua Spine 1, c2 qua Spine 2; gọi đúng tên flow-splitting | G4/W6 | Chờ kiểm tra |
| **E03** | Client/server request/response theo tham số, 1/2/4/8 flow từ 2 client | TV2 | `workload/`, config đã validate, `client-requests.csv`, `server-events.jsonl`, summary có `load_sustained` | TV4 | Mỗi mức tải: mọi request mong đợi có status; ID/size khớp client–server; rate thực đạt được đánh dấu; mã thoát đúng | G3/W4 | Chưa làm (tuần 1 mới có bài thử 1 flow) |
| **E04** | RTT, throughput, per-link utilization có raw, đơn vị, cửa sổ; `d_trans = L/R` minh bạch | TV3 | Raw ping/iperf3/counter, CSV sinh bằng mã, `metrics-spec.md` | TV1 | Mọi metric có công thức + đơn vị + cửa sổ; CSV đối chiếu được raw (sha256); không có 0 thay dữ liệu thiếu | W6 | Chưa làm (tuần 1 có bài đo chẩn đoán) |
| **E05** | Detect đúng link; test bão hòa và test tải thấp | TV3 | `monitoring/detect.py`, `tests/test_detection.py`, log alert | TV4 | Ca quá tải chỉ ra đúng link; ca tải thấp không cảnh báo; rule/threshold công bố trước khi đo chính | W7 | Chưa làm |
| **E06** | Recommend theo rule minh bạch, có lý do | TV3 | `monitoring/recommend.py`, test rule | TV1 | Mỗi khuyến nghị có điều kiện đo được + lý do; không hứa cải thiện trước khi Verify; không khuyến nghị khi cả hai đường bão hòa | W8 | Chưa làm |
| **E07** | Apply có xác nhận, Ignore không đổi, log old/new | TV1 | `apply.jsonl`, flow dump trước/sau, test Ignore/thiếu confirm/busy/lỗi | TV4 | Thiếu confirm hoặc Ignore → flow table không đổi; Apply đổi đúng preset, verify lại đường đi, rollback khi lỗi | G5/W9 | Chờ kiểm tra |
| **E08** | Compare A/B cùng tải, ≥ 3 lần, thống kê có nguồn | TV3 | `analysis/compare.py`, `results/summary.csv`, raw từng lượt | TV1 | Chỉ ghép cặp cùng `config_id` và `load_sustained=true`; % delta + độ dao động; nêu cả trường hợp không cải thiện | G6/W10 | Chưa làm |
| **E09** | Tái lập từ VM sạch bằng README + script | TV1 | README, setup log, kết quả chạy trên máy thành viên khác | TV4 | Người khác clone, setup, chạy verify + workload + đo theo README không cần thao tác ngầm; số liệu không chỉnh tay | G7/W12 | Đang làm |
| **E10** | Báo cáo đúng 2 chương; protocol/OSI-TCP/IP, metric, AI networking; AI log nếu dùng AI | TV4 | `report/`, `docs/ai-prompts-verification-log.md` | TV1 | Đủ 1.1–1.5 và 2.1–2.5; số liệu truy được tới run_id; trích dẫn có nguồn; AI log có prompt/lỗi/kiểm chứng | G7/W12 | Chưa làm |

### 4.1. Bảng vấn đề → chức năng → bằng chứng

| Vấn đề | Hệ quả | Chức năng | Bằng chứng kiểm thử |
|---|---|---|---|
| Không có môi trường tái lập | Mỗi lần đo một khác | Testbed cố định topology/link/workload, script + README, version cấu hình (F01, F08) | Chạy lại ≥ 3 lần, **báo cáo độ dao động** (E08), tái lập trên máy khác (E09) |
| Benchmark không giống inference | Số liệu không phản ánh request/response | Generator có tham số (F02) | Log request/response theo từng lượt (E03) |
| Đo rời rạc | Không biết link nào nghẽn | Metric theo flow/link, detect theo luật (F03, F04) | Ca quá tải đúng link; ca tải thấp không cảnh báo (E05) |
| Thử cấu hình rủi ro | Ngại thay đổi | Preset A/B, Apply có xác nhận, chỉ trong testbed (F06) | Log before/after; Ignore không đổi gì (E07) |
| Không chứng minh hiệu quả | Quyết định cảm tính | Verify và Compare cùng offered load (F07) | Bảng A/B, % delta, kể cả không cải thiện (E08) |
| Nhiễu từ GPU/LLM | Lẫn độ trễ xử lý vào độ trễ mạng | Server emulator với service delay **đo được**; tách `app_response_ms` = `server_proc_ms` + `network_residual_est_ms` | Log có cả ba giá trị cho từng request (E03, E04) |

## 5. Cấu trúc báo cáo hai chương (phân công viết, TV4 tổng hợp, TV1 duyệt)

| Mục | Nội dung chính | Người viết chuyên môn |
|---|---|---|
| 1.1 | Kiến trúc Spine–Leaf, so với 3-tier, oversubscription | TV1 |
| 1.2 | Đặc thù lưu lượng AI inference, request/response | TV2 |
| 1.3 | Nghẽn mạng: capacity, throughput, utilization, RTT, `d_trans`, queueing, loss | TV3 |
| 1.4 | Giám sát, phát hiện theo luật, human-in-the-loop | TV3 |
| 1.5 | Mininet/OVS, VM, công cụ đo, rủi ro timing | TV1 |
| 2.1 | Bối cảnh **giả định**, hiện trạng, RQ1–RQ3 | TV4 |
| 2.2 | Yêu cầu F01–F08, I/O, P0/P1 | TV4 |
| 2.3 | Kiến trúc, topology, protocol stack, sequence Apply | TV1, TV2 |
| 2.4 | Hiện thực, kịch bản T01–T05, biến kiểm soát | TV2, TV3 |
| 2.5 | Kết quả, thảo luận, trả lời RQ, giới hạn | TV3 |

## 6. Quy ước dự án

### 6.1. Cấu trúc repository

```text
docs/            đặc tả và hướng dẫn (env-matrix, network-handoff, workload-spec, metrics-spec, scope-rubric, ai log)
topology/ control/   hạ tầng mạng, Apply (TV1)
workload/        client/server, config, runner (TV2)
measurement/     công cụ đo, chuyển raw → CSV (TV3); monitoring/, analysis/ từ tuần 6
qa/              checker, biên bản review, bản nháp issue (TV4)
tools/           helper dùng chung (evidence, thống kê)
tests/           unit test chạy được không cần Mininet
scripts/         setup/verify hạ tầng
evidence/<khu-vực>/<run_id>/   minh chứng từng lượt (không sửa sau khi tạo)
results/raw|summary|figures/   dữ liệu thí nghiệm chính thức (từ tuần 4)
report/ slides/  báo cáo, slide (tuần 8+)
```

### 6.2. Đặt tên lượt chạy và file

- `run_id = <UTC YYYYMMDDTHHMMSSffffffZ>-<label>`; `label` chỉ gồm chữ thường, số, `-`, `_`, tối đa 40 ký tự, gợi ý `<tvN>-<việc>[-rerun]`. Thư mục evidence = `evidence/<khu-vực>/<run_id>/`.
- Khu vực evidence: `week1/` và `network/` của TV1 (**giữ nguyên, không sửa**), `tv2-week1/`, `tv3-week1/`, `tv4-week1/`; từ tuần 4 dữ liệu thí nghiệm ở `results/raw/<run_id>/`.
- `config_id` theo [workload-spec §2](workload-spec.md#2-định-danh-và-thời-gian-thống-nhất-với-tv3); `profile ∈ {A, B}`.
- Tên file: chữ thường, `-` ngăn cách (`client-requests.csv`); cột CSV/trường JSON: `snake_case` có hậu tố đơn vị.

### 6.3. Đơn vị và hậu tố

| Hậu tố | Đơn vị | Ví dụ |
|---|---|---|
| `_ms`, `_ns`, `_s`/`_sec` | mili giây, nano giây, giây | `app_response_ms`, `send_mono_ns`, `warmup_sec` |
| `_utc` | chuỗi ISO-8601 UTC, đuôi `Z` | `send_utc` |
| `_mono_ns` | đồng hồ monotonic, chỉ dùng tính khoảng | `recv_mono_ns` |
| `_bytes`, `_pkts` | byte, gói | `req_size_bytes`, `tx_dropped_pkts` |
| `_mbps` | 10^6 bit/s | `receiver_goodput_mbps` |
| `_rps` | request/s | `rate_rps_per_flow` |
| `_pct` | phần trăm 0–100 | `icmp_loss_pct` |

Số thập phân trong CSV/JSON dùng dấu chấm; tài liệu tiếng Việt có thể viết dấu phẩy.

### 6.4. Thư mục minh chứng

Mỗi lượt bắt buộc có: `result.json` (thành công/thất bại, kiểm tra), `exit-code.txt`, `environment.json` (máy, kernel, gói, boot ID, commit), `source-manifest.json` (SHA-256 mã đã chạy), raw output nguyên văn, CSV sinh bằng mã (nếu có). Mỗi khu vực có `README.md` mô tả lệnh, máy thực hiện và kết quả. Lượt thất bại được **giữ nguyên** kèm giải thích; sửa xong thì tạo lượt mới, không ghi đè.

### 6.5. Git, PR và review

- Nhánh: `tvN/N18-0XX-mo-ta-ngan`. Commit nhỏ, thông điệp nói *thay đổi gì và vì sao*.
- Mỗi PR theo [mẫu PR](../.github/pull_request_template.md): nội dung thay đổi, lệnh tái lập, môi trường/phiên bản, mã nguồn, raw log, CSV (nếu có), **AI Prompts & Verification Log** nếu dùng AI hỗ trợ code. PDF chỉ để đọc, không thay nguồn và minh chứng.
- Reviewer theo phân công: TV2 ← TV3; TV3 ← TV1; TV4 ← TV2 (TV1 phê duyệt phạm vi); TV1 ← TV4. Reviewer ghi kết luận bằng PR review hoặc biên bản trong `qa/`.
- Không merge khi lỗi bắt buộc chưa sửa và kiểm tra lại.

### 6.6. Trạng thái công việc

| Trạng thái | Khi nào | Ai chuyển |
|---|---|---|
| `Chưa làm` | Chưa có sản phẩm | — |
| `Đang làm` | Đang làm, chưa đủ bằng chứng | DRI |
| `Chờ kiểm tra` | Đủ đầu ra + minh chứng theo cột “Bằng chứng”, đã mở PR/biên bản | DRI, TV4 cập nhật tracker |
| `Hoàn thành` | Reviewer xác nhận đạt; lỗi bắt buộc đã sửa và kiểm tra lại | TV4 cập nhật **sau** khi có review đạt |
| `Bị chặn` | Kẹt > 48 giờ, đã báo TV1 | DRI, TV1 chỉ định hỗ trợ |

### 6.7. Issue và board

- Mỗi task có một issue `N18-0XX — <tên>` gồm checklist nghiệm thu, link sản phẩm, reviewer; nhãn `week-1`, `TV2|TV3|TV4`, `status:*`. Phát hiện khi review ghi thành comment/issue riêng, khi đóng phải dẫn commit sửa và kết quả kiểm tra lại.
- Board GitHub Projects gồm cột theo §6.6. Bản nháp ba issue tuần 1 ở [`qa/issues/`](../qa/issues/).

## 7. Điều kiện đóng tuần 1 và trạng thái hiện tại

| Điều kiện | Trạng thái 18/11/2026 |
|---|---|
| Đủ tài liệu đã sửa và dữ liệu bài thử thật của TV2, TV3, TV4 | Đã có; bài thử chạy trên VM TV1 — mỗi thành viên **vẫn phải tự chạy và giải thích** |
| Tài liệu TV2–TV3 thống nhất schema và ý nghĩa metric | Đã đối chiếu: cùng `run_id/config_id/profile`, cùng tên `app_response_ms/server_proc_ms/network_residual_est_ms`; checker TV4 xác nhận CSV đủ cột |
| Reviewer xác nhận bằng biên bản/PR; lỗi bắt buộc đã sửa và kiểm tra lại | Phát hiện F1/F2 đã sửa và kiểm tra lại; **chữ ký review TV3, TV1, TV2 còn trống** |
| TV1 phê duyệt phạm vi/rubric của TV4 | **Chưa** |
| Tracker phản ánh bằng chứng | N18-002/003/004 → `Chờ kiểm tra`; chỉ chuyển `Hoàn thành` sau review đạt |
| G1 | **Chưa chốt** — TV1 chốt khi N18-001…004 đều đạt |

Biên bản chi tiết: [qa/week1-review.md](../qa/week1-review.md).

## 8. Bài thử khởi động TV4: kiểm tra log

Phương án đã chọn: **kiểm tra log**. [`qa/check_week1_logs.py`](../qa/check_week1_logs.py) đọc lại raw/CSV **độc lập** với mã đang được kiểm tra (không import `workload/` hay `measurement/`) và đối chiếu: ID/số byte từng request giữa log client và server của TV2; từng mẫu RTT, số gói, goodput và khoảng đo giữa raw và CSV của TV3; tính lại nearest-rank; SHA-256 raw.

```bash
python3 qa/check_week1_logs.py --tv2 evidence/tv2-week1/<run> --tv3 evidence/tv3-week1/<run> \
  --out evidence/tv4-week1/$(date -u +%Y%m%dT%H%M%S%6NZ)-tv4-logcheck
```

Kết quả: lần đầu **22/24 đạt**, phát hiện F1, F2 → sửa ở commit `af83849` → kiểm tra lại **25/25 đạt**. Xem [evidence/tv4-week1](../evidence/tv4-week1/README.md).

## 9. Thay đổi so với bản nháp v0

| Bản nháp v0 (PDF) | v1.0 |
|---|---|
| Ngân hàng X, 3.000 nhân viên, GPU 40 % viết như sự kiện | Ghi rõ **giả định minh họa** |
| Chỉ có bối cảnh, RQ, giải pháp, bảng vấn đề | Thêm phạm vi P0/P1/ngoài phạm vi, rubric **E01–E10** (chủ trì, bằng chứng, review, điều kiện đạt), cấu trúc báo cáo, quy ước tên/đơn vị/minh chứng/PR/trạng thái, board |
| “Server emulator không chạy LLM, nên RTT đo được là của mạng” | Thời gian ứng dụng gồm service delay; tách `server_proc_ms` và `network_residual_est_ms` |
| “Chạy lại ≥ 3 lần, độ dao động thấp (E09)” | Báo cáo độ dao động (E08), tái lập trên máy khác (E09); không đặt “dao động thấp” làm điều kiện đạt |
| “B chia qua hai Spine” | B là static flow-splitting theo subnet client, không gọi ECMP |
