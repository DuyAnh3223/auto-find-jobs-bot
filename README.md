# Facebook Group Monitor — Windows V1

Ứng dụng cá nhân: mở các group đã cấu hình bằng Edge/Chrome, đọc một lượng bài giới hạn,
lọc từ khóa, lưu SQLite và xuất Excel/CSV. Giao diện Python + CustomTkinter, bộ đọc Playwright,
đóng gói bằng PyInstaller. Tham khảo cách dùng browser profile và đọc feed trong
[`demo/bot-condo`](demo/bot-condo/), không phụ thuộc hoặc sửa demo đó.

## Chạy bản Windows

Mở `dist/FacebookGroupMonitor/FacebookGroupMonitor.exe` sau khi build.
**Bản mới nhất:** `dist/fast-review-o/FacebookGroupMonitor/FacebookGroupMonitor.exe`.
Đóng app cũ trước khi mở bản này; cấu hình/profile dùng lại.
Khi chuyển sang máy khác, **chép cả thư mục `FacebookGroupMonitor`, gồm `_internal`**.
Máy cần Windows 10/11 64-bit và Microsoft Edge hoặc Google Chrome đã cài.
Đây là bản đóng gói theo thư mục, chưa ký số và chưa có installer.

1. Bấm **Thêm group**, nhập link `https://www.facebook.com/groups/ten-hoac-id`, đặt tên hiển thị.
2. Chọn các group và nhóm nghề SWE, IT Helpdesk/Support bằng checkbox.
   Địa điểm HCM và mức intern/fresher là tiêu chí cố định của profile này.
   Cấu hình từ khóa cũ vẫn được lưu để truy vết nhưng không còn là ô chỉnh bộ lọc.
3. Chọn Edge hoặc Chrome. Bấm **Mở Facebook để đăng nhập**.
4. Tự đăng nhập/xác minh trong cửa sổ trình duyệt của bot, rồi bấm **Đã đăng nhập** trên ứng dụng.
   Bot xác nhận phiên rồi đóng trình duyệt để lưu profile. Không nhập mật khẩu vào ứng dụng.
5. Bấm **START**: quét ngay một lượt, sau đó tự quét theo khoảng đã cấu hình.
6. Chọn bài để xem đầy đủ; nhấp đúp hoặc bấm **Mở bài Facebook** để mở bằng trình duyệt mặc định.
   Bảng bên trái chỉ có ngày phát hiện, group và từ khóa. Nội dung chi tiết nằm ở cột lớn bên phải,
   chữ lớn hơn và có thanh cuộn riêng. Kéo vạch ngăn giữa bảng và nội dung để thay đổi độ rộng.
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
- Bộ phân loại dùng cụm từ có biên từ, chuẩn hóa Unicode và bỏ dấu cho profile việc làm.
  `intern` không khớp `internal`; `java` không khớp `javascript`. Công nghệ đứng riêng chỉ là
  bằng chứng phụ, cần chức danh/nhiệm vụ SWE hoặc IT support.
- Một bài chỉ phù hợp khi cùng vị trí có ngành mục tiêu, level intern/fresher và địa điểm HCM.
  Bài thiếu bằng chứng được đưa vào **Cần xem lại**; bài sai ngành/level/địa điểm bị loại khỏi danh sách chính.
- Nút **Đánh giá lại bài đã lưu** cho phép xem trước rồi áp dụng classifier mới. Hash, ngày phát hiện,
  quyết định lưu xem xét và hồ sơ ứng tuyển được giữ nguyên.
  Đánh giá chạy nền có tiến độ; **STOP** hủy trước khi hoàn tất transaction và giữ đánh giá cũ.
  Khi đổi nhóm nghề hoặc phiên bản bộ lọc, nhãn cũ nằm ở **Cần đánh giá lại**.
  Danh sách mặc định chỉ hiện **Phù hợp**; chọn **Cần xem lại** để đọc bài thiếu bằng chứng.
- Phân loại lưu kèm family, level, location, lý do và phiên bản classifier; Excel có các cột này.
- Lịch sử phân trang 100 bài. Ô tìm kiếm hỗ trợ nội dung, tên group và từ khóa; SQLite LIKE mặc định
  chỉ bỏ qua hoa thường đầy đủ cho ASCII, nên tìm lịch sử tiếng Việt có thể phân biệt hoa thường.
- Nút **Excel/CSV** xuất toàn bộ kết quả khớp ô tìm kiếm, không chỉ trang đang xem.
  File tự động `results.xlsx` chỉ chứa bài phù hợp theo tiêu chí hiện tại, chưa bị bỏ qua.
  Xuất thủ công dùng các bộ lọc đang chọn; chọn Cần xem lại nếu muốn xuất riêng nhóm này.
- Nếu đang mở `results.xlsx` bằng Excel, Windows có thể khóa file. Đóng file để lượt sau cập nhật được.
  Bot ghi file tạm rồi thay thế, giữ bản cũ nếu thay thế thất bại.
- Nếu toàn bộ group đều lỗi đọc và chưa lưu/cập nhật bài nào, giữ nguyên file Excel.
  Nếu đã lưu/cập nhật được bài trước khi lỗi, vẫn xuất các bài đó và ghi rõ lượt quét chưa đầy đủ.
- Ô văn bản có dấu mở đầu công thức được thêm dấu nháy để tránh thực thi công thức từ bài đăng.
  Excel giới hạn 32.767 ký tự/ô: nội dung dài được cắt có thông báo, bản đầy đủ vẫn ở SQLite/CSV.
- Profile chứa phiên đăng nhập nhạy cảm: không chia sẻ profile hoặc đưa vào Git. Đổi trình duyệt
  cần đăng nhập lại; bot không sử dụng profile Chrome/Edge cá nhân đang mở của bạn.

## Giới hạn Facebook cần biết

- Tự chạy khi đăng nhập Windows: chạy `windows-startup.ps1` để đăng ký, hoặc thêm `-Disable`
  để tắt. Giữ nguyên thư mục bản exe đã đăng ký. Windows mở bot với `--autostart` và tự START.
  Mỗi lần mở tiến trình bot mới quét **60 bài/group** ngay, sau đó **20 bài/group mỗi 30 phút**.
  STOP/START trong cùng cửa sổ không lặp lượt sâu đã chạy; đóng rồi mở bot và START sẽ chạy sâu lại.
  Bản nâng cấp chuyển cấu hình lịch cũ sang 60/20/30 một lần; sau đó có thể chỉnh và lưu tùy ý.
  Giờ 07:00 và dấu hoàn tất theo ngày không còn điều khiển lịch. Máy phải đăng nhập Windows,
  không ngủ, và phiên Facebook còn hợp lệ. Hết phiên Facebook thì bot dừng để bạn đăng nhập lại.
  Khoảng quét tính từ đầu lượt; lượt kéo dài hơn khoảng đặt sẽ nghỉ thêm trọn khoảng sau khi xong.

- Bot yêu cầu đăng nhập, kể cả khi theo dõi group công khai. Chỉ đọc nội dung phiên đó truy cập được.
- Mở feed với yêu cầu sắp xếp thời gian; Facebook có thể không tuân theo thứ tự này.
  “Bài mới” ở V1 là **bài mới phát hiện trong phần feed giới hạn**, không phải cam kết quét đủ mọi bài.
  Lượt đầu có thể lưu bài cũ; bài ghim và bài bị đẩy xuống sâu có thể ảnh hưởng độ bao phủ.
- Tối đa 40 vòng đọc/cuộn/group; dừng ngay khi đủ số bài hợp lệ đã đặt, hoặc sau
  5 vòng liên tiếp không đọc thêm được bài hợp lệ chưa gặp trong lượt hiện tại.
  Bài không khớp từ khóa và bài đã lưu ở lượt trước vẫn tính là tiến triển.
  Có thêm bài thì bộ đếm 5 vòng trở về 0; thẻ thiếu nội dung/link không tính vào số bài mục tiêu.
  Nhật ký báo số bài thực tế/mục tiêu và lý do dừng; dừng theo giới hạn hoặc không có tiến triển
  chỉ là thông tin, không tự tạo cảnh báo nếu không có lỗi/thẻ đọc thiếu.
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

## Duyệt bài và theo dõi ứng tuyển

- Danh sách mặc định **HCM** chỉ hiện bài nhận diện có HCM/TP.HCM/Hồ Chí Minh/Sài Gòn
  và qua bộ lọc vị trí/kinh nghiệm. **Chưa rõ địa điểm** xem riêng.
  Bài nhận diện ngoài HCM được bỏ qua trước khi lưu kết quả mới. Bài ngoài HCM đã lưu trước đây
  không hiện trong danh sách, kể cả khi chọn Tất cả; hồ sơ ứng tuyển giữ nguyên.
  Bài đã đánh giá **Không phù hợp** theo vị trí hoặc kinh nghiệm cũng không được lưu mới;
  dữ liệu cũ loại này được ẩn khỏi toàn bộ bộ lọc.
  Bot vẫn phải đọc nội dung để nhận diện địa điểm; số bài mục tiêu tính cả bài bị loại.
  Ba bộ lọc độc lập: **Địa điểm** (HCM/Chưa rõ địa điểm/Tất cả),
  **Đánh giá** (Tất cả/Phù hợp/Cần xem lại), **Xử lý**. Mặc định HCM + Tất cả + Chưa xử lý.
  Excel tự động chỉ xuất nhóm HCM;
  xuất thủ công theo bộ lọc đang chọn. Hồ sơ ứng tuyển đã lưu vẫn giữ nguyên.
  Nhận diện ưu tiên dòng ghi nơi làm việc; bài tuyển HCM và nơi khác vẫn giữ.
  Đây là quy tắc văn bản, không hiểu hết ngữ cảnh, không đọc địa chỉ trong ảnh;
  địa danh chưa nhận diện được nằm ở nhóm chưa rõ, không khẳng định là ngoài HCM.
- **Kiểm tra group (N)** mở danh sách cảnh báo ngay trong cửa sổ chính: lỗi/gián đoạn,
  thẻ thiếu nội dung/link, thẻ đổi/timeout.
  Hiển thị thời gian, số bài đọc thực tế, URL và nút **Mở group**, **Đã kiểm tra**.
  Group chưa tới lượt khi dừng hoặc mở trình duyệt thất bại được ghi **Chưa hoàn tất**.
  Cảnh báo lưu trong SQLite qua lần khởi động; mỗi group giữ thông tin gần nhất,
  lượt quét mới không tự xóa group khỏi danh sách. **Đã kiểm tra** xác nhận cảnh báo hiện tại;
  phát sinh cảnh báo ở lượt sau sẽ hiện lại. Đây không phải bảo đảm không bỏ sót bài.
  Chỉ đạt giới hạn bài/lượt cuộn là thông tin trong nhật ký, không tạo cảnh báo.
  Bản mới tự bỏ các cảnh báo cũ chỉ có lý do đạt giới hạn; giữ cảnh báo có lỗi đọc.
  Lượt đọc bình thường không xóa lỗi cũ chưa được bạn đánh dấu **Đã kiểm tra**.
- Danh sách cấu hình group chỉ hiện ô chọn, tên và nút **Xóa**. Rê chuột lên tên để xem URL;
  nhấp đúp tên để mở group bằng trình duyệt mặc định, dùng được cả khi đang quét.
- Với khoảng 50 group có 10–60 bài/ngày theo thống kê của bạn, cấu hình khởi điểm là
  **15 bài/group, mỗi 30 phút** khi chạy liên tục. Đây là mức thử nghiệm, không bảo đảm không bỏ sót.
  Nếu lượt quét gần hoặc vượt 30 phút, tăng khoảng lên 40–45 phút; nếu ổn định dưới 15 phút,
  có thể thử mỗi 20 phút. Bài đăng có thể dồn đợt; sau thời gian ngừng chạy cần quét sâu hơn.
  Giới hạn bài là tối đa, reader có thể kết thúc sớm do giới hạn cuộn hoặc thẻ không đọc được.
  Khoảng quét tính từ đầu lượt; nếu quá hạn, bot nghỉ thêm trọn khoảng cấu hình sau khi quét xong.
- Danh sách bài có bộ lọc **Đánh giá** (Phù hợp/Cần xem lại) và **Xử lý**
  (Chưa xử lý/Đã lưu/Đã bỏ qua/Tất cả). Nhãn đánh giá là kết quả lọc tự động;
  việc lưu hoặc bỏ qua là quyết định của bạn.
- Khi duyệt bài: `Q`/`E` sang bài trước/sau, `Y` lưu **Đang xem xét** và chọn bài tiếp,
  `D` bỏ qua và chọn bài tiếp, `O` mở bài Facebook đang chọn, `Ctrl+Z` hoàn tác thao tác lưu hoặc bỏ qua gần nhất.
  Phím không hoạt động khi con trỏ đang ở ô nhập liệu.
- **Đang xem xét** dành cho tin đáng chú ý nhưng chưa ứng tuyển; chưa bắt buộc công ty,
  vị trí hay ngày ứng tuyển. Khi đổi sang trạng thái ứng tuyển hoặc phỏng vấn, công ty và vị trí là bắt buộc.
- Màn hình Theo dõi ứng tuyển nằm trong cửa sổ chính. `Q`/`E` chuyển hồ sơ,
  `D` xóa hồ sơ hiện tại sau khi xác nhận, `Ctrl+S` lưu, `Ctrl+Z` hoàn tác lưu/xóa gần nhất.
  Bấm ô **Xóa** ở cuối từng dòng để xóa chính hồ sơ đó.
- Cột **Theo dõi** trong danh sách bài cập nhật trạng thái hồ sơ và tô xanh bài đã lưu.
  Nội dung trùng ở group khác vẫn liên kết cùng hồ sơ.
## Quy tắc lọc và gom bài

Bản đóng gói hiện tại: `dist/fast-review-o/FacebookGroupMonitor/FacebookGroupMonitor.exe`.

- Ba nhóm điều kiện độc lập: vị trí/công nghệ, địa điểm và kinh nghiệm. Từ khóa trong cùng nhóm là OR; các nhóm đã nhập phải cùng đạt (AND). Nhóm để trống được xem là không giới hạn.
- Cột **Đánh giá** ghi Phù hợp hoặc Cần xem lại. Bộ lọc giúp ưu tiên đọc, còn Lưu xem xét/Bỏ qua là quyết định xử lý của bạn.
- Bài có cùng nội dung sau khi chuẩn hóa Unicode, viết thường và gom khoảng trắng dùng chung một SHA-256. Một dòng kết quả hiện tất cả group và link nguồn.
- Quét lại cùng URL cập nhật nội dung và lần thấy gần nhất, nhưng giữ ngày phát hiện đầu tiên. Nếu nội dung đã sửa, quyết định thủ công được xóa và bài được đánh giá lại.
- Quyết định bỏ qua được lưu theo hash. Excel tự động chỉ xuất các bài có đánh giá **Phù hợp** và **Cần xem lại**.

## Theo dõi ứng tuyển

Bản có chức năng này: `dist/fast-review-o/FacebookGroupMonitor/FacebookGroupMonitor.exe`.
Đóng app cũ trước khi mở bản mới. Cấu hình, phiên đăng nhập và dữ liệu bài đăng được giữ lại.

- Bấm **Theo dõi ứng tuyển** → **+ Hồ sơ mới** để nhập job thủ công.
- Hoặc dùng `Y` khi duyệt bài để tạo hồ sơ **Đang xem xét**, điền sẵn link và nội dung bài.
  Một tin nhiều vị trí có thể tạo nhiều hồ sơ.
- Lưu công ty, vị trí, ngày ứng tuyển, trạng thái, lịch phỏng vấn, địa điểm/link họp,
  tên HR, email, điện thoại/Zalo và ghi chú. Công ty và vị trí bắt buộc từ trạng thái **Đã ứng tuyển** trở đi.
- Ngày ứng tuyển: `DD/MM/YYYY`; lịch phỏng vấn: `DD/MM/YYYY HH:MM`, theo giờ máy tính.
  Lưu lịch hẹn hiện tại; các vòng trước có thể ghi trong phần ghi chú. Chưa có thông báo nhắc lịch.
- Trạng thái: Đang xem xét, Đã ứng tuyển, Đã hẹn phỏng vấn, Đã phỏng vấn, Nhận offer, Bị từ chối, Đã rút.
  Tìm kiếm hoặc lọc trạng thái, chọn hồ sơ để sửa, bấm **Lưu hồ sơ** để ghi thay đổi.
- Hồ sơ nằm trong bảng `applications` của `monitor.db`, không bị cập nhật bởi lượt quét Facebook.
  Xóa toàn bộ `monitor.db` sẽ xóa cả hồ sơ ứng tuyển; hãy sao lưu trước khi reset dữ liệu.
- Excel kết quả quét vẫn chỉ chứa bài đăng; hồ sơ ứng tuyển được lưu và xem trong app.
- Theo dõi ứng tuyển hiển thị ngay trong cửa sổ chính. Bấm **← Danh sách bài** để quay lại;
  chuyển qua lại giữ nguyên các ô đang nhập, bấm **Lưu hồ sơ** để lưu bền vững.
- Cột **Theo dõi** hiển thị trạng thái hồ sơ; các dòng có hồ sơ được tô xanh.
  Bản trùng nội dung ở group khác cũng nhận trạng thái. Hồ sơ cũ được liên kết qua link nguồn.
  Hồ sơ nhập thủ công cần có link bài để hiện trạng thái tương ứng trong danh sách.
