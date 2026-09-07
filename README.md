# Facebook Group Monitor — Windows V1

Ứng dụng cá nhân: mở các group đã cấu hình bằng Edge/Chrome, đọc một lượng bài giới hạn,
lọc từ khóa, lưu SQLite và xuất Excel/CSV. Giao diện Python + CustomTkinter, bộ đọc Playwright,
đóng gói bằng PyInstaller. Tham khảo cách dùng browser profile và đọc feed trong
[`demo/bot-condo`](demo/bot-condo/), không phụ thuộc hoặc sửa demo đó.

## Chạy bản Windows

Mở `dist/FacebookGroupMonitor/FacebookGroupMonitor.exe` sau khi build.
**Bản sửa đọc feed mới nhất:** `dist/feed-fix-3/FacebookGroupMonitor/FacebookGroupMonitor.exe`
(tiêu đề cửa sổ có chữ **Feed fix 3**). Đóng app cũ trước khi mở bản này; cấu hình/profile dùng lại.
Khi chuyển sang máy khác, **chép cả thư mục `FacebookGroupMonitor`, gồm `_internal`**.
Máy cần Windows 10/11 64-bit và Microsoft Edge hoặc Google Chrome đã cài.
Đây là bản đóng gói theo thư mục, chưa ký số và chưa có installer.

1. Bấm **Thêm group**, nhập link `https://www.facebook.com/groups/ten-hoac-id`, đặt tên hiển thị.
2. Chọn các group muốn theo dõi bằng checkbox; nhập mỗi từ khóa trên một dòng.
3. Chọn Edge hoặc Chrome. Bấm **Mở Facebook để đăng nhập**.
4. Tự đăng nhập/xác minh trong cửa sổ trình duyệt của bot, rồi bấm **Đã đăng nhập** trên ứng dụng.
   Bot xác nhận phiên rồi đóng trình duyệt để lưu profile. Không nhập mật khẩu vào ứng dụng.
5. Bấm **START**: quét ngay một lượt, sau đó tự quét theo khoảng đã cấu hình.
6. Chọn bài để xem đầy đủ; nhấp đúp hoặc bấm **Mở bài Facebook** để mở bằng trình duyệt mặc định.
7. Bấm **STOP** để dừng lịch và yêu cầu kết thúc lượt đang chạy. App đợi thao tác trình duyệt
   hiện tại kết thúc trước khi đóng profile; có thể cần khoảng 15–20 giây hoặc lâu hơn khi trình duyệt lỗi.

Mặc định **20 phút/lượt, 30 bài/group**, tự cập nhật `exports/results.xlsx` sau mỗi lượt hoàn tất.
Khoảng cấu hình: 10–1440 phút, 1–100 bài/group. Bắt đầu thử với 2–3 group trước khi tăng số lượng.
Không có bảo đảm một tần suất hay số group cụ thể sẽ không bị Facebook hạn chế.

Lịch tính từ lúc bắt đầu lượt trước. Nếu lượt quét kéo dài hơn khoảng cấu hình, bot chờ thêm
một khoảng đầy đủ sau khi xong; không chạy bù liên tiếp và không chạy chồng. Chỉ một phiên ứng dụng
được dùng cùng thư mục dữ liệu. Máy phải bật, có mạng và không ngủ; đóng app là dừng lịch.
Mở lại app cần bấm START; V1 không tự chạy cùng Windows và không phải Windows Service.

## Dữ liệu và kết quả

Dữ liệu mặc định tại `%LOCALAPPDATA%\FacebookGroupMonitor`:

```text
monitor.db                  # Cấu hình và các bài khớp từ khóa
browser-profiles/msedge/    # Profile Facebook riêng của Edge
browser-profiles/chrome/    # Profile Facebook riêng của Chrome
exports/results.xlsx       # Toàn bộ lịch sử, cập nhật sau mỗi lượt hoàn tất
logs/monitor.log            # Log xoay vòng, 2 MB/file và 3 bản cũ
app.lock                    # Khóa ngăn mở hai app trên cùng dữ liệu
```

- **SQLite là dữ liệu chính**. Lỗi xuất Excel không làm mất những bài đã lưu.
- Cấu hình được lưu khi bấm **Lưu cấu hình**, đăng nhập, START hoặc đóng app bình thường.
  Hãy STOP trước khi sửa cấu hình. Xóa group/từ khóa không xóa lịch sử bài đã tìm được.
- Kết quả gồm tên group do bạn đặt, group URL, từ khóa khớp, post URL, nội dung,
  thời gian đăng nếu đọc được, nhãn thời gian gốc, ngày phát hiện và lần thấy gần nhất.
- Lưu thời gian xác định được theo UTC; giao diện/Excel hiển thị giờ địa phương của máy,
  file xuất kèm độ lệch múi giờ. Đặt Windows ở UTC+7 nếu muốn giờ Việt Nam.
- Nếu chỉ thấy “2 giờ”, giữ nguyên chuỗi đó; **không gán giờ phát hiện làm giờ đăng**.
- URL bài là khóa chống trùng. Thấy lại bài khớp thì cập nhật nội dung/từ khóa,
  giữ ngày phát hiện đầu tiên. Bài giống nội dung nhưng khác URL vẫn là hai bài.
- Lọc cụm từ dạng chứa, không phân biệt hoa thường; chuẩn hóa Unicode và khoảng trắng/xuống dòng.
  Vẫn phân biệt dấu tiếng Việt. `java intern` khớp `JAVA\nINTERN`; `java` cũng có thể khớp `javascript`.
  Không dùng AI, không yêu cầu từ khóa xuất hiện nguyên một từ, chưa có từ khóa loại trừ.
- Chỉ lưu bài đang khớp tại lúc đọc. Sửa từ khóa áp dụng cho các lượt sau; không tìm lại toàn bộ
  lịch sử Facebook. Bài cũ đã lưu không tự bị xóa khi sửa nội dung hoặc không còn khớp.
- Lịch sử phân trang 100 bài. Ô tìm kiếm hỗ trợ nội dung, tên group và từ khóa; SQLite LIKE mặc định
  chỉ bỏ qua hoa thường đầy đủ cho ASCII, nên tìm lịch sử tiếng Việt có thể phân biệt hoa thường.
- Nút **Excel/CSV** xuất toàn bộ kết quả khớp ô tìm kiếm, không chỉ trang đang xem.
  File tự động `results.xlsx` luôn chứa toàn bộ lịch sử.
- Nếu đang mở `results.xlsx` bằng Excel, Windows có thể khóa file. Đóng file để lượt sau cập nhật được.
  Bot ghi file tạm rồi thay thế, giữ bản cũ nếu thay thế thất bại.
- Nếu toàn bộ group đều lỗi đọc và chưa lưu/cập nhật bài nào, giữ nguyên file Excel.
  Nếu đã lưu/cập nhật được bài trước khi lỗi, vẫn xuất các bài đó và ghi rõ lượt quét chưa đầy đủ.
- Ô văn bản có dấu mở đầu công thức được thêm dấu nháy để tránh thực thi công thức từ bài đăng.
  Excel giới hạn 32.767 ký tự/ô: nội dung dài được cắt có thông báo, bản đầy đủ vẫn ở SQLite/CSV.
- Profile chứa phiên đăng nhập nhạy cảm: không chia sẻ profile hoặc đưa vào Git. Đổi trình duyệt
  cần đăng nhập lại; bot không sử dụng profile Chrome/Edge cá nhân đang mở của bạn.

## Giới hạn Facebook cần biết

- Bot yêu cầu đăng nhập, kể cả khi theo dõi group công khai. Chỉ đọc nội dung phiên đó truy cập được.
- Mở feed với yêu cầu sắp xếp thời gian; Facebook có thể không tuân theo thứ tự này.
  “Bài mới” ở V1 là **bài mới phát hiện trong phần feed giới hạn**, không phải cam kết quét đủ mọi bài.
  Lượt đầu có thể lưu bài cũ; bài ghim và bài bị đẩy xuống sâu có thể ảnh hưởng độ bao phủ.
- Tối đa 10 vòng tải/cuộn/group; thẻ không đủ nội dung/link cũng tiêu thụ giới hạn để tránh quét vô hạn.
  Không dừng chỉ vì thấy bài đã lưu bởi feed có thể không theo thời gian.
- Mở “Xem thêm”/“See more” trong phần nội dung bài. Chưa hỗ trợ OCR ảnh, video, bình luận,
  lấy tác giả, thông báo đẩy hoặc website tuyển dụng.
- Chỉ chấp nhận permalink xác định được. Link phải có group ID/slug khớp nguồn cấu hình.
  Nếu group dùng slug nhưng permalink trả ID số khác, thử cấu hình group bằng ID số.
- Không lấy toàn bộ text của thẻ làm phương án dự phòng để tránh lưu nhầm bình luận hoặc tên người
  thành nội dung bài. Vì vậy nếu Facebook đổi selector, có thể phải cập nhật `monitor/facebook.py`.
- Bản Feed fix 2 nhận diện thẻ con của feed có phần nội dung bài, thay vì chỉ dựa vào `role="article"`
  (thuộc tính này có thể nằm ở placeholder rỗng). Rê chuột vào liên kết thời gian để Facebook gán permalink;
  href chỉ có query được giải quyết theo URL group hiện tại. Không bấm liên kết/bình luận để lấy URL.
  Lỗi đọc phân biệt số thẻ phát hiện, thiếu nội dung và thiếu permalink.
- Feed fix 3 giữ tham chiếu đến từng thẻ DOM trong mỗi vòng, thay cho truy cập vị trí `nth()`
  sau khi danh sách đã thay đổi. Thẻ bị xóa/thay thế hoặc timeout thao tác được bỏ qua;
  vòng tiếp theo lấy lại danh sách. Log đếm riêng các lần này. Bản thân lỗi trình duyệt,
  mất phiên và lỗi lưu dữ liệu không bị coi là thẻ bị thay đổi.
- Hết phiên/chuyển đến đăng nhập hoặc checkpoint: dừng lịch, yêu cầu đăng nhập thủ công lại.
  Group không đọc được: ghi lỗi, tiếp tục group khác. Không coi feed không đọc được là lượt thành công rỗng.
- Cookie và URL chỉ là dấu hiệu phiên, không chứng minh chắc chắn mọi hình thức xác minh đều đã hoàn tất.
  Bot không tự giải CAPTCHA hoặc vượt kiểm soát truy cập.

## Chạy từ source

Cần Python 3.12+ có Tkinter. PowerShell tại thư mục dự án:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Bot dùng kênh `msedge`/`chrome` đã cài trên Windows, không cần tải Chromium riêng.
Môi trường kiểm tra cục bộ của lần phát triển này nằm trong `.tools`/`.venv`, không đưa vào bản phân phối.
Có thể chạy `.\run.ps1`, hoặc mở trực tiếp file exe.

## Kiểm thử và đóng gói

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check monitor main.py tests
.\.venv\Scripts\python.exe main.py --smoke-test --data-dir .test-data\gui
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Test browser yêu cầu Edge. Bộ test đọc HTML mẫu cục bộ qua Playwright route, không truy cập
tài khoản hoặc group Facebook thật. Chỉ chạy phần không cần browser: `-m "not browser"`.
`--data-dir` có thể dùng để tách dữ liệu thử nghiệm. `--smoke-test` kiểm tra GUI ẩn,
SQLite/Excel riêng và Playwright với trang HTML trong Edge headless rồi tự đóng,
ghi `smoke-ok.txt` nếu thành công, không mở Facebook. Chế độ này yêu cầu Edge đã cài.

Checklist triển khai và chấp nhận:

- [x] Thêm/xóa/bật/tắt group; chỉnh từ khóa, khoảng quét, giới hạn bài; lưu cấu hình.
- [x] Giao diện Start/Stop, đăng nhập thủ công bằng profile riêng, worker nền và khóa một phiên app.
- [x] Lọc nhiều từ khóa, SQLite, chống trùng, lịch sử, mở link, Excel/CSV.
- [x] Test logic lưu trữ, lọc từ khóa, xuất file, lịch quét và lỗi phiên đăng nhập.
- [x] 30 kiểm thử tự động qua; gồm GUI và 7 kiểm thử Edge với HTML mẫu. Ruff qua.
- [x] Build `.exe` thành công; chạy smoke test từ chính `.exe` qua GUI, SQLite, Excel và Playwright/Edge.
- [x] Kiểm tra Facebook thật với profile người dùng ngày 07/09/2026: cả 8 group trong log lỗi đã đọc được.
  Mỗi group giới hạn 3 thẻ, tổng cộng 23 bài hợp lệ và 1 thẻ thiếu dữ liệu; 1 bài khớp bộ từ khóa đang cấu hình.
  Kết quả thử được lưu riêng tại `.test-data/live-results`, không ghi vào lịch sử chính của người dùng.
- [x] Feed fix 3: thử group 146k với giới hạn 30 bài và 10 vòng cuộn; đọc 24 bài hợp lệ,
  1 bài khớp từ khóa, bỏ qua 1 thẻ thiếu dữ liệu, không có timeout trong lượt thử.
  Test HTML riêng tái hiện thẻ bị xóa/thay thế khi hover hoặc mở rộng và xác nhận đọc tiếp đúng bài.
- [ ] UAT: đăng nhập Facebook thật, đóng và mở lại app vẫn dùng được phiên.
- [ ] UAT: đối chiếu link/nội dung/thời gian với bài thực tế của 2–3 group mục tiêu.
- [ ] UAT: chạy ít nhất hai lượt 20 phút; xác nhận bài mới, chống trùng, Excel.
- [ ] UAT: STOP giữa lượt; hết phiên; group không truy cập được; file Excel đang mở.
- [ ] UAT: copy cả thư mục build sang máy Windows khác và chạy không cần Python.
- [ ] Nguồn website tuyển dụng trong tương lai.

Kết quả tự động trên được kiểm tra ngày 07/09/2026, trên máy phát triển Windows hiện tại;
không thay thế các bước UAT Facebook thật và máy Windows khác còn để trống.

Bản sửa đăng nhập 07/09: vòng chờ người dùng tiếp tục xử lý sự kiện Playwright, thay vì
chặn dispatcher bằng `threading.Event.wait`. Có test request phát sinh sau khi trang đăng nhập
đã tải để kiểm tra hồi quy. Trình duyệt bật Chromium sandbox. Test Edge bật sandbox cần chạy
ngoài môi trường terminal hạn chế quyền. Chưa xác nhận bản sửa giải quyết trang xác minh Facebook thật.
Tham khảo [Playwright về chờ chặn luồng](https://playwright.dev/python/docs/library#timesleep-leads-to-outdated-state).

Điểm mở rộng nguồn: giữ đối tượng `Post`, bộ lọc, SQLite và exporter; thêm reader cho website
rồi nối vào worker. V1 chưa tạo hệ thống plugin hoặc bộ khung đa nguồn khi chưa có website cụ thể.

Tài liệu kỹ thuật tham khảo:
[Playwright browser channels](https://playwright.dev/python/docs/browsers),
[persistent context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context),
[CustomTkinter packaging](https://github.com/TomSchimansky/CustomTkinter/wiki/Packaging).
