# NHÓM 18 — BỘ TÀI LIỆU GỐC TRIỂN KHAI 12 TUẦN

**Cập nhật tuần 1:** môi trường và bài thử hai host của TV1 đã có minh chứng. N18-001 ở trạng thái **Chờ kiểm tra** bởi TV4. TV2 xem [hướng dẫn môi trường và bàn giao](docs/env-matrix.md), [log kiểm thử](evidence/week1/README.md) và [README chính](README.md).

## Bắt đầu từ đâu?

1. **`Nhom18_De_cuong_chi_tiet.pdf`**: đọc nhanh để thống nhất tên đề tài cô đề xuất, bối cảnh, bài toán, input/output, 2 chương báo cáo, giới hạn sản phẩm và tiêu chí nghiệm thu.
2. **`Nhom18_De_cuong_chi_tiet.md`**: bản sửa được, dùng làm source of truth cho phạm vi và cấu trúc báo cáo.
3. **`Nhom18_Phan_cong_Checklist_12_tuan.md`**: xem phân công TV1–TV4, 48 task bắt buộc, các mốc kỹ thuật và minh chứng cần có.
4. **`Nhom18_Progress_Tracker.xlsx`**: cập nhật mỗi tuần theo công việc. Sửa cột `Trạng thái`, thêm `Link/đường dẫn thực tế` và người review; sheet `Tổng quan` tính tiến độ tự động.

## Quy tắc khóa phạm vi

Prototype chạy trên Mininet/Open vSwitch trong VM Ubuntu, mô phỏng lưu lượng request–response; phát hiện nghẽn theo rule; khuyến nghị và áp dụng cấu hình **sau xác nhận của operator**; chạy lại để đối chiếu A/B. **Không triển khai self-healing, AI controller, thiết bị production hoặc LLM/GPU thật.**

## Công bằng công việc

TV1–TV4 là mã tạm vì chưa có tên thành viên. Mỗi người có 12 task P0 (51 điểm ước lượng) trong 12 tuần và một task P1 tùy chọn. Mỗi task có tiêu chí nghiệm thu và bằng chứng; chỉ đánh dấu xong sau review chéo. Công sức thực tế có thể lệch so với điểm ước lượng, nhóm được điều chỉnh phân công qua họp tuần.

## Cần lưu ý

- N18-001 đã có script và log kiểm thử, đang chờ TV4 review. Các task khác giữ trạng thái theo tracker; chưa có kết quả topology 10 node hoặc thực nghiệm A/B.
- Nếu sử dụng AI hỗ trợ viết code/script, phải lưu `AI Prompts & Verification Log` theo yêu cầu môn học.
- Mốc tuần chỉ là tuần 1–12 tính từ khi bắt đầu triển khai; không giả định lịch thực tế của nhóm.
