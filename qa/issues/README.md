# Bản nháp issue và board tuần 1

Ba file dưới đây là nội dung issue cho board tuần 1. Tạo trên GitHub (cần quyền ghi repo; TV1 hỗ trợ quyền nếu cần):

```bash
gh label create week-1 --color 0E8A16 --force
gh label create "status:cho-kiem-tra" --color FBCA04 --force
for n in 002 003 004; do
  gh issue create --title "$(head -1 qa/issues/N18-$n.md | sed 's/^# //')" \
    --body-file qa/issues/N18-$n.md --label week-1 --label "status:cho-kiem-tra"
done
```

Board GitHub Projects (cột: Chưa làm, Đang làm, Chờ kiểm tra, Hoàn thành, Bị chặn) cần token có scope `project` (`gh auth refresh -s project`), sau đó `gh project create --owner <owner> --title "Nhom18 — 12 tuần"` và `gh project item-add`. Khi đã tạo, ghi link issue vào cột `Link/đường dẫn thực tế` của tracker.

Phát hiện khi review được ghi thành comment trong issue tương ứng; khi đóng phải dẫn commit sửa và kết quả kiểm tra lại (xem [biên bản](../week1-review.md)).
