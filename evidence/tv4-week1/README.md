# Minh chứng TV4 tuần 1 — kiểm tra log (N18-004)

**Phương án bài thử:** kiểm tra log. [`qa/check_week1_logs.py`](../../qa/check_week1_logs.py) đọc lại raw/CSV độc lập với mã của TV2/TV3 và đối chiếu ID/số byte (TV2), raw ↔ CSV (TV3).

**Máy thực hiện:** VM `Nhom18-W1` (Ubuntu 24.04 ARM64) trên Mac của TV1, ngày 18/11/2026, do phiên hỗ trợ AI chạy theo yêu cầu của người dùng — không phải TV4 chạy trên máy của TV4.

## Lệnh

```bash
python3 qa/check_week1_logs.py \
  --tv2 evidence/tv2-week1/20261118T112728069663Z-tv2-smoke \
  --tv3 evidence/tv3-week1/20261118T112952839193Z-tv3-probe-rerun \
  --out evidence/tv4-week1/$(date -u +%Y%m%dT%H%M%S%6NZ)-tv4-logcheck
```

Không cần quyền root hay testbed đang chạy; chạy được cả trên macOS.

## Các lượt

| Thư mục | Commit checker | Đầu vào | Kết quả |
|---|---|---|---|
| [20261118T112845394713Z-tv4-logcheck](20261118T112845394713Z-tv4-logcheck/qa-report.md) | `6d7df69` | TV2 `…112728…-tv2-smoke`, TV3 `…112753…-tv3-probe` | **KHÔNG ĐẠT 22/24**: F1 (min/mean ping), F2 (khoảng đo iperf3 11,0 s) |
| [20261118T113009015094Z-tv4-logcheck-recheck](20261118T113009015094Z-tv4-logcheck-recheck/qa-report.md) | `af83849` | TV2 `…112728…-tv2-smoke`, TV3 `…112952…-tv3-probe-rerun` | **ĐẠT 25/25** |
| [20261118T113030251138Z-unit-tests](20261118T113030251138Z-unit-tests/unit-tests.log) | `af83849` | `python3 -m unittest discover -s tests -v` trên VM | **30/30 OK** |

Lần đầu thất bại được giữ nguyên. Phát hiện, commit sửa và kết quả kiểm tra lại ghi trong [qa/week1-review.md](../../qa/week1-review.md) và bản nháp issue [N18-003](../../qa/issues/N18-003.md).

Ngoài checker, mã trong `source-manifest.json` của 4 lượt TV2/TV3 được so với Git blob của commit ghi trong `environment.json` của chính lượt đó: 21/21 file (TV2) và 15/15 file (TV3) khớp ở cả hai commit.
