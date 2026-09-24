# Implementation plan: SWE và IT Helpdesk/Support tại HCM, Intern/Fresher

Ngày: 2026-09-24
Trạng thái: IN PROGRESS — classifier, worker, storage, UI và export đã triển khai bước đầu; UAT PENDING.
Phạm vi: repository `D:\dev\bot-crawler`.

## 1. Mục tiêu và căn cứ

Giảm bài sai ngành trong danh sách chính, đồng thời nhận được các cách gọi khác nhau của công việc SWE và IT Helpdesk/Support ở HCM, nhận intern/fresher.

Yêu cầu trực tiếp của người dùng:
- Hai nhóm mục tiêu: SWE và IT Helpdesk/Support.
- Địa điểm: HCM.
- Cấp độ: intern/fresher.
- Nhận các chức danh/công nghệ tương đương, không phụ thuộc một cụm từ duy nhất.

Review trước khi lập plan đã đọc code và SQLite thực tế ở chế độ chỉ đọc:
- Cấu hình vị trí có các cụm chỉ nói về kinh nghiệm như `không yêu cầu kinh nghiệm`, `tuyển fresher`.
- Trong 6.640 bản ghi tại thời điểm review, 1.118 bản ghi chỉ khớp các từ khóa kinh nghiệm chung được kiểm tra; 483 mang nhãn suitable, 592 review, 43 unsuitable. Đây không phải tỷ lệ sai đã gắn nhãn của toàn bộ dữ liệu; có bản ghi trùng giữa các group.
- Đã thấy HR, ngân hàng, kinh doanh và CSKH vận chuyển vào suitable.
- Đã tái hiện bằng cấu hình thực tế: `intern` khớp `internal`; `1 năm kinh nghiệm` khớp `11 năm kinh nghiệm`; `senior` trong câu hướng dẫn intern làm loại bài đúng.
- 18 test hiện có liên quan keyword/location/classification PASS ở lần review; chưa đủ bao phủ yêu cầu mới. Chưa kiểm chứng quét Facebook trực tiếp.

Implementation checkpoint (2026-09-24):
- Đã thêm `monitor/job_taxonomy.py` và `monitor/job_matching.py` với matching có boundary, evidence, family/level/location và kết quả JSON.
- Worker chuyển `keywords=None` để `read_group` chuyển mọi bài đọc được đến classifier, kể cả bài sửa không còn từ khóa; cập nhật bài đã tồn tại khi chuyển unsuitable.
- SQLite có metadata classifier; `Store.reclassify_posts()` hỗ trợ preview/apply và giữ lịch sử người dùng.
- UI có đánh giá lại bài đã lưu và hiển thị bằng chứng; Excel có cột family/level/location/reason.
- Checkpoint sửa review: classifier `job-profile-4`; hỗ trợ alias SWE/SDE/dev, chức danh phần mềm tiếng Việt (thực tập sinh phần mềm, thực tập sinh phát triển phần mềm), level graduate, và cơ chế chuyển IT/CNTT chưa rõ nhiệm vụ vào Cần xem lại (`it_tasks_unclear`). Technology trong nội dung không tự biến Data/Operations/Content/Product Intern thành SWE; địa điểm HCM và ngoài HCM xung đột được chuyển vào Cần xem lại.
- Cấu hình chọn nhóm nghề có tác dụng trong classifier và fingerprint. Từ khóa/kinh nghiệm cũ vẫn lưu để truy vết nhưng không còn là điều khiển chỉnh được; HCM và intern/fresher là chính sách cố định.
- Đánh giá lại chạy nền có tiến độ/STOP; hủy hoặc lỗi cập nhật giữa transaction rollback toàn bộ. Nhãn cũ được đánh dấu cần đánh giá lại. Danh sách mặc định suitable, Excel tự động chỉ xuất suitable còn hiệu lực và chưa bỏ qua.
- Automated verification: 125 non-browser tests PASS; 8 browser fixture tests PASS trên Edge headless; Ruff PASS; 50 cụm thử nghiệm HCM đạt 100% kỳ vọng (34 Phù hợp, 13 Cần xem lại, 3 Bị loại do không có ngành nghề).
- Không thay database người dùng. Chưa đóng gói exe mới, chưa đo precision/recall trên tập bài người dùng gắn nhãn, chưa chạy Facebook live; UAT PENDING. Các quy tắc phân loại là heuristic và còn cần nghiệm thu trên dữ liệu thực.

Các điểm tích hợp hiện tại:
- `monitor/core.py`: Settings, normalize, match_keywords, classify_content, job_location, Post.
- `monitor/facebook.py`: read_group chỉ chuyển bài có keyword hit đến worker.
- `monitor/worker.py`: scan_once phân loại, bỏ unsuitable trước khi lưu, tự xuất Excel.
- `monitor/storage.py`: cấu hình JSON, posts, trạng thái bot/người dùng, nhóm bản trùng, applications.
- `monitor/app.py`: nhập tiêu chí, lọc danh sách, hiển thị đánh giá, xuất thủ công.
- `monitor/exporter.py`, `monitor/saved_posts_ui.py`, `monitor/tracking_ui.py`: xuất dữ liệu và luồng đã lưu/ứng tuyển.

## 2. Hợp đồng hành vi đề xuất

Các lựa chọn dưới đây là thiết kế đề xuất để triển khai, chưa phải xác nhận UAT của người dùng.

### REQ-01 — Đánh giá từng vị trí

Một vị trí phù hợp khi đồng thời có bằng chứng:

`(SWE OR IT_HELPDESK_SUPPORT) AND ENTRY_LEVEL AND HCM`

Ba thuộc tính phải thuộc cùng vị trí hoặc phần thông tin chung áp dụng rõ ràng cho vị trí đó. Không ghép ngành của vị trí A với level/địa điểm của vị trí B.

Kết quả cấp bài:
- `suitable`: ít nhất một vị trí đáp ứng đủ ba điều kiện.
- `review`: có bằng chứng ngành mục tiêu nhưng thiếu/không chắc level, địa điểm hoặc ranh giới vị trí; không có vị trí suitable.
- `unsuitable`: không có vị trí thuộc ngành mục tiêu, hoặc mọi vị trí mục tiêu đều có mâu thuẫn rõ ràng về level/địa điểm.
- Bài chỉ có dấu hiệu kỹ thuật yếu được review, không suitable. Bài chỉ có từ kinh nghiệm không đủ điều kiện vào review.
- Bài không phải tuyển dụng (tìm việc, bán khóa học, quảng cáo) không suitable; trường hợp không xác định được ý định thì review nếu có ngữ cảnh ngành đủ rõ.

### REQ-02 — Hai nhóm nghề và alias

| Nhóm | Bằng chứng mạnh | Bằng chứng cần ngữ cảnh |
|---|---|---|
| SWE | software engineer/developer, lập trình viên, backend/frontend/fullstack developer, web/mobile/application developer | developer/dev, backend/frontend/fullstack đứng riêng, Java, Spring, Node.js, .NET, Python, React, Flutter... |
| IT Helpdesk/Support | IT helpdesk, IT support, desktop support, end-user computing support, hỗ trợ CNTT | technical support, service desk, nhân viên IT, kỹ thuật PC, IT intern/TTS IT |

- Từ công nghệ đứng riêng chỉ là bằng chứng phụ; cần chức danh hoặc nhiệm vụ phát triển phần mềm.
- Support chung/CSKH không chứng minh IT support. Dùng nhiệm vụ hỗ trợ thiết bị, hệ điều hành, tài khoản, mạng, người dùng để xác nhận nhóm này.
- Business Developer/Business Development không là SWE. QA/tester, BA, data, sales, marketing, CSKH không tự động được tính vào hai nhóm mục tiêu.
- Không blacklist toàn bài vì có từ sales/marketing/senior: có thể là nhiệm vụ phối hợp hoặc một vị trí khác.
- Chỉ thêm alias có test ngữ cảnh; không mở rộng tùy ý các nghề lân cận.

### REQ-03 — Level

- Nhận intern, internship, fresher, fresh graduate, thực tập/thực tập sinh/TTS, mới tốt nghiệp, không yêu cầu kinh nghiệm khi gắn với vị trí.
- `0–1 năm` cho phép người chưa có kinh nghiệm: có thể đạt điều kiện entry nếu không có yêu cầu bắt buộc mâu thuẫn trong cùng vị trí.
- `ưu tiên có 1 năm kinh nghiệm` không phải yêu cầu tối thiểu; tự nó cũng không chứng minh nhận fresher.
- `bắt buộc/tối thiểu 1 năm` và yêu cầu kinh nghiệm cao hơn không tự coi là fresher. Junior/entry-level chung chung chưa đủ rõ thì review.
- `dưới 1 năm` nhưng không nêu nhận người chưa có kinh nghiệm: review.
- Phân tích số, khoảng, đơn vị năm/tháng và từ bắt buộc/ưu tiên; không so khớp chuỗi con số.
- Senior/lead trong chức danh là bằng chứng level; senior trong câu hướng dẫn/mentoring không là level của ứng viên.
- Thông tin mâu thuẫn chưa giải quyết được phải review, không suitable.

### REQ-04 — Địa điểm

- Dùng địa điểm làm việc của vị trí, ưu tiên trường/đoạn rõ ràng; không lấy trụ sở, địa chỉ liên hệ hay hashtag để ghi đè nơi làm việc.
- Hỗ trợ alias HCM/TP.HCM/HCMC/Hồ Chí Minh/Sài Gòn và cách viết không dấu.
- Bài cho phép cùng vị trí làm tại HCM hoặc thành phố khác: HCM là lựa chọn hợp lệ.
- Nhiều vị trí ở nhiều thành phố: ghép theo vị trí; chưa chắc thì review.
- Địa danh chưa ánh xạ chắc chắn và địa chỉ chỉ có quận/phường: review; không mặc định HCM.
- Bài chỉ ghi remote không tự đáp ứng HCM. Remote cho ứng viên tại HCM có bằng chứng rõ ràng có thể phù hợp.
- Danh mục địa danh phải có nguồn/phạm vi và khả năng cập nhật; không hardcode mọi địa danh lân cận thành ngoài HCM mà chưa kiểm tra ý nghĩa địa chỉ hiện hành. Lưu tên gốc và bằng chứng khi có nhập nhằng.

### REQ-05 — Giải thích, danh sách và xuất dữ liệu

- Mặc định danh sách chính là suitable; review nằm trong bộ lọc riêng có số lượng.
- Hiện nhóm nghề, chức danh, level, nơi làm việc và trích đoạn chứng minh; lý do thiếu/mâu thuẫn cho review/unsuitable.
- Bài nhiều vị trí vẫn một dòng bài, phần chi tiết liệt kê từng vị trí và kết quả tương ứng.
- Excel tự động mặc định xuất suitable; xuất review là lựa chọn rõ ràng. Xuất tự động/thủ công dùng cùng chính sách và có cột lý do.
- Tìm kiếm ô nội dung trong danh sách chỉ thu hẹp kết quả; không thay thế bộ phân loại nghề.
- Bài đã lưu xem xét và hồ sơ ứng tuyển vẫn truy cập được dù đánh giá mới là unsuitable.

### REQ-06 — Dữ liệu và cấu hình

- Cấu hình tách nhóm nghề, alias nghề/công nghệ và tiêu chí level; từ khóa kinh nghiệm không được dùng làm bằng chứng nghề.
- Bảo toàn cấu hình cũ để truy vết; chuyển các từ khóa kinh nghiệm đã nhận diện sang đúng nhóm. Từ tùy chỉnh chưa hiểu được để vô hiệu hóa/chờ phân loại, không tiếp tục OR tự do vào ngành.
- Không thay đổi group, lịch quét, profile trình duyệt hoặc dữ liệu ứng tuyển trong migration.
- Chuẩn hóa phục vụ matching không thay đổi `normalized_content`/`content_hash`: tránh gộp lại lịch sử và mất liên kết ứng tuyển.
- Đánh giá lại chỉ cập nhật kết quả máy; giữ nội dung, URL, hash, detected_at, last_seen_at, user_decision và applications.

## 3. Thiết kế kỹ thuật

### Bộ phân loại thuần Python

Tách module mới `monitor/job_matching.py` và từ điển `monitor/job_taxonomy.py` (tên có thể điều chỉnh theo kích thước thực tế). Không thêm dịch vụ AI/network dependency trong vòng triển khai đầu.

Pipeline:
1. Giữ nguyên văn bản gốc và ranh giới dòng; tạo bản chuẩn hóa matching Unicode/case/dấu/khoảng trắng riêng.
2. Tokenize/canonicalize cụm từ có dấu câu: C++, C#, .NET, Node.js, full-stack, IT-support. Kiểm tra biên từ; không dùng `\b` đơn giản cho mọi công nghệ.
3. Tách khối vị trí theo heading, danh sách đánh số và cấu trúc tuyển dụng. Nhận phần yêu cầu/địa điểm chung chỉ khi phạm vi áp dụng rõ.
4. Trích role family, title, recruitment intent, level, experience constraints, location và evidence trong từng khối.
5. Áp dụng quy tắc REQ-01..04; tổng hợp cấp bài bằng quy tắc xác định, không để điểm cộng bù một điều kiện bắt buộc bị sai.

Contract đề xuất:
- `MatchResult`: status, reason_codes, matched_families, jobs, classifier_version, criteria_fingerprint.
- `JobMatch`: title, family, level, location, status, reasons, evidence.
- `Evidence`: field, original_snippet, block_index (offset gốc nếu cần); không trả offset của văn bản đã bỏ dấu như offset nguyên bản.
- Wrapper `classify_content` trả status để duy trì tương thích trong quá trình chuyển đổi; đường quét chính dùng toàn bộ MatchResult.
- Một chính sách duy nhất cho phân loại, UI và export; tránh UI tiếp tục loại bằng `job_location` cũ sau khi classifier mới đã nhận đúng vị trí.

### Đường thu thập bài

Thay cổng `read_group -> match_keywords -> on_post` bằng chuyển từng bài đọc được đến worker để đánh giá một lần. Với giới hạn bài/group hiện tại, không cần chặn bằng danh sách cụm từ cũ trước classifier.

- Giữ cơ chế DOM extraction, canonical URL, chống lặp trong lượt, stop và giới hạn đọc.
- Đếm riêng read/suitable/review/rejected/unreadable; số matched không đại diện tổng số bài đọc.
- Lưu suitable/review mới; bài bị loại mới chỉ ghi thống kê, không tích lũy toàn bộ feed không liên quan.
- Nếu URL đã tồn tại, lần quét mới phải cập nhật đánh giá kể cả thành unsuitable; không return sớm để giữ nhãn suitable cũ.
- Nếu nội dung bài thay đổi, giữ quy tắc cập nhật nội dung hiện có trừ khi phát hiện xung đột cần nêu riêng; thao tác reclassify không đi qua đường upsert làm đổi timestamps/user_decision.

### SQLite và đánh giá lại

- Thêm cột `classification_json`, `classifier_version`, `criteria_fingerprint`, `classified_at` với default tương thích dữ liệu cũ; giữ `bot_status` để giảm phạm vi thay đổi.
- Dùng connection theo operation như Store hiện tại, không chia sẻ connection GUI/worker.
- Reclassify chạy nền khi không quét; tính kết quả trước, cập nhật trong transaction. Hủy/lỗi trước commit giữ đánh giá cũ; báo số bài và trạng thái rõ.
- Ngăn đổi cấu hình trong lượt reclassify; mọi kết quả dùng cùng snapshot tiêu chí.
- Khi đổi classifier/tiêu chí, nhãn cũ có fingerprint khác phải được đánh dấu cần cập nhật; không hiển thị như đánh giá mới đã xác nhận.
- Cung cấp dry-run so sánh old/new và phân bố lý do trước apply. Áp dụng dữ liệu thật sau khi bản sao vượt kiểm tra migration/invariants.
- Backup SQLite qua SQLite backup API hoặc lúc app đã đóng; không copy riêng file `.db` khi WAL đang hoạt động. Rollback bằng snapshot cùng phiên bản app tương thích.

## 4. Các bước triển khai và checkpoint

### Bước 1 — Baseline và bộ ca chuẩn

- Kiểm tra git status, hướng dẫn scoped nếu được thêm sau này, đường dữ liệu và entrypoint bản đóng gói đang sử dụng.
- Chạy test hiện có; ghi lỗi nền riêng. Không sửa unrelated failures trong cùng thay đổi.
- Tạo fixture từ các lỗi đã tái hiện và bài thực đã ẩn thông tin liên hệ; không commit DB/profile/log riêng tư.
- Viết test hành vi REQ-01..04 trước bộ phân loại mới, xác nhận test thất bại đúng nguyên nhân.
- Checkpoint: các ca sai/đúng có expected rõ; baseline và giới hạn được ghi lại.

### Bước 2 — Matcher và classifier

- Implement chuẩn hóa riêng, phrase boundary, taxonomy, tách vị trí, level/location và evidence.
- Ưu tiên đảm bảo bài một vị trí; bài tổng hợp chưa tách được trả review có lý do thay vì đoán suitable.
- Chạy unit test theo ma trận bên dưới; không thay đổi hash/dedup helper.
- Checkpoint: classifier thuần không phụ thuộc Tk/SQLite/browser và mọi ca bắt buộc PASS.

### Bước 3 — Cấu hình, lưu trữ và worker

- Version cấu hình, migration từ tiêu chí cũ, schema additive và serialize MatchResult.
- Thay cổng substring trước worker; thống nhất đường đánh giá và export tự động.
- Implement cập nhật bài đã tồn tại bị loại, dry-run/reclassify và phát hiện đánh giá cũ.
- Test DB cũ, migration lặp lại, rollback khi lỗi, preserves hashes/decisions/applications và stop giữa lượt.
- Checkpoint: chạy trên DB tạm/bản sao; chưa tác động DB đang dùng.

### Bước 4 — UI và export

- UI chọn hai nhóm nghề; chỉnh alias nâng cao theo loại, không trộn level vào role.
- Thêm lọc nhóm nghề, mặc định suitable, review riêng; hiện evidence từng vị trí.
- Thêm thao tác xem trước/đánh giá lại, tiến độ, lỗi và trạng thái tiêu chí đã đổi.
- Giữ luồng Y lưu xem xét, D bỏ qua, Ctrl+Z và tạo/xem hồ sơ; dữ liệu cũ bị loại vẫn vào được từ màn hình saved/tracking.
- Đồng bộ xuất tự động/thủ công và cập nhật test exporter/UI tương ứng.
- Checkpoint: GUI smoke bằng data-dir tạm, không dùng profile Facebook thật cho smoke.

### Bước 5 — Đo chất lượng, đóng gói và UAT

- Đánh giá bộ bài độc lập đã gắn nhãn; xem false positive và false negative theo từng nhóm nghề.
- Chạy toàn bộ test phù hợp, lint, browser fixture nếu Edge sẵn có; ghi NOT VERIFIED cho phần không chạy được.
- Build vào thư mục phiên bản mới; smoke bản exe với data-dir tạm; cập nhật README theo hành vi/lệnh/build path thực tế.
- Backup và dry-run dữ liệu thật, đối chiếu rồi apply trong lượt triển khai được yêu cầu; không tự khởi động quét Facebook khi chỉ làm offline verification.
- Quét thử một lượt giới hạn khi thực hiện UAT được cho phép; không thay đổi lịch/giới hạn quét để bù chất lượng lọc.
- Checkpoint cuối: báo riêng implementation, automated checks, dữ liệu thật, browser live và UAT. Chỉ human sign-off mới đóng UAT PENDING.

## 5. Acceptance criteria và test bắt buộc

| ID | Trường hợp | Kết quả yêu cầu |
|---|---|---|
| AC-01 | HR/CSKH/ngân hàng tại HCM + không yêu cầu kinh nghiệm | unsuitable; không đạt ngành |
| AC-02 | Java Backend Intern tại HCM; React Frontend Fresher; thực tập lập trình viên không dấu | suitable, family SWE |
| AC-03 | IT Helpdesk Fresher tại HCM; TTS IT có nhiệm vụ hỗ trợ PC/mạng/người dùng | suitable, family IT_HELPDESK_SUPPORT |
| AC-04 | Customer Support vận chuyển; Business Developer Intern | unsuitable; không nhầm nghề |
| AC-05 | Java Developer + internal recruitment team, không nêu level | review; internal không phải intern |
| AC-06 | Developer bắt buộc 11 năm hoặc 2–3 năm; tối thiểu 12 tháng | unsuitable; không khớp 1 năm/entry |
| AC-07 | Java Intern được senior hướng dẫn | suitable nếu HCM rõ |
| AC-08 | SWE 0–1 năm tại HCM, không có yêu cầu tối thiểu mâu thuẫn | suitable; nhận ứng viên chưa có kinh nghiệm |
| AC-09 | SWE chỉ ghi junior hoặc ưu tiên 1 năm kinh nghiệm | review nếu chưa có bằng chứng nhận fresher |
| AC-10 | Senior Java + Marketing Intern cùng bài | không suitable cho SWE intern |
| AC-11 | Java Intern HCM + Senior Java Hà Nội | suitable; nêu đúng vị trí HCM |
| AC-12 | Backend Intern Hà Nội + Marketing Intern HCM | unsuitable cho mục tiêu; không ghép chéo |
| AC-13 | Trụ sở HCM, vị trí làm việc rõ ràng tại Hà Nội | unsuitable |
| AC-14 | Địa chỉ thiếu thành phố, remote chung, khối nhiều vị trí chưa tách chắc | review nếu có nghề mục tiêu |
| AC-15 | Tin khóa học Java/tìm việc cá nhân có intern/HCM | không suitable tuyển dụng |
| AC-16 | `C++`, `C#`, `.NET`, `Node.js`, `full-stack`, help desk và biến thể dấu | matching đúng; Java không tự khớp JavaScript |
| AC-17 | Job chỉ ghi Software Engineer / Backend, level nằm ở dòng yêu cầu | không bị loại bởi cổng cụm từ liền nhau cũ |
| AC-18 | Bài đang suitable được quét lại thành senior-only | cập nhật unsuitable, không giữ nhãn cũ |
| AC-19 | Reclassify dữ liệu cũ, lặp lại hoặc lỗi/hủy | nhất quán; không đổi hash/timestamps/user_decision/applications |
| AC-20 | Bài đã lưu/đang ứng tuyển bị classifier mới loại | vẫn xem được tại saved/tracking |
| AC-21 | Cùng nội dung ở nhiều group | vẫn gộp đúng; evidence và nhãn nhất quán |
| AC-22 | Cùng filter xuất tự động/thủ công | tập kết quả và lý do nhất quán |
| AC-23 | Đổi tiêu chí nhưng chưa reclassify | báo đánh giá cũ; không coi kết quả cũ là đã đạt tiêu chí mới |

### Bộ dữ liệu đánh giá chất lượng

- Chuẩn bị tối thiểu 200 nội dung không trùng; lấy từ bài đã lưu và, khi có, mẫu đã đọc nhưng bị bộ cũ bỏ qua. Dữ liệu đã lưu bị thiên lệch bởi bộ lọc cũ nên không đủ đo recall toàn feed.
- Có tối thiểu 30 bài đúng SWE, 30 bài đúng helpdesk/support nếu thu thập đủ; phần còn lại gồm sai ngành, sai level, sai nơi làm việc, bài tổng hợp và thiếu dữ kiện. Nếu thiếu mẫu phải báo rõ, không suy diễn tỷ lệ.
- Gắn nhãn ở cấp vị trí và cấp bài; bài thiếu thông tin có nhãn unknown/review, không ép thành đúng/sai. Cần người dùng xác nhận nhãn dùng cho nghiệm thu.
- Chia tuning/holdout theo nội dung trước điều chỉnh quy tắc; bản gần trùng không nằm ở hai phía. Không chỉnh quy tắc bằng holdout rồi báo đó là đánh giá độc lập.
- Mục tiêu đề xuất: precision suitable >= 90% trên holdout; tỷ lệ bỏ sót bài đúng <= 10% khi tính suitable + review, báo riêng cho SWE và helpdesk. Đồng thời báo tỷ lệ bài đúng bị đẩy vào review để không che việc classifier né quyết định.
- Đây là ngưỡng nghiệm thu đề xuất, không phải hiệu năng đã đo. Báo tử số/mẫu số, số review và giới hạn lấy mẫu; không gọi một bộ mẫu nhỏ là chất lượng toàn bộ Facebook.

## 6. Verification và UAT

Lệnh tham chiếu, chạy từ repository root; điều chỉnh lựa chọn test theo marker thực tế:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -m "not browser" -q
.\.venv\Scripts\python.exe -m pytest tests/test_browser.py -m browser -q
.\.venv\Scripts\python.exe -m ruff check monitor tests main.py
.\.venv\Scripts\python.exe main.py --smoke-test
```

Không coi smoke có liên quan Edge là đã xác nhận Facebook live. Kiểm tra `build.ps1` trước khi chọn lệnh build để không ghi đè bản đang chạy.

Manual UAT:
1. Mở bản mới với dữ liệu đã backup; kiểm tra groups/lịch quét/profile và hồ sơ vẫn còn.
2. Chọn SWE + IT Helpdesk/Support, HCM, intern/fresher; preview reclassify và xem lý do thay đổi.
3. Kiểm tra HR/ngân hàng/CSKH mẫu cũ rời danh sách suitable; mở được bài đã lưu và hồ sơ liên quan.
4. Kiểm tra mỗi nhóm nghề ít nhất 5 bài suitable và 5 review/rejected, gồm bài nhiều vị trí.
5. Chạy lượt quét giới hạn, kiểm tra bài thực trên Facebook với evidence trong app; xác nhận STOP hoạt động.
6. Xuất Excel, đối chiếu với filter và lý do; mở lại app kiểm tra tính bền vững.
7. Người dùng xác nhận chất lượng và các chính sách entry-level/remote; nếu thay đổi chính sách, cập nhật plan và test trước khi đổi code.

## 7. Phạm vi không làm trong đợt đầu

- Không triển khai LLM/embedding, OCR bài ảnh, tìm kiếm toàn Facebook hay tăng tốc/tần suất quét.
- Không tự ứng tuyển/gửi tin nhắn, không thay hệ thống theo dõi hồ sơ.
- Không xóa lịch sử hoặc bài người dùng đã lưu vì classifier đánh giá lại.
- Không commit/push hoặc thay DB/cấu hình thực tế trong bước lập plan này.

Gợi ý chia thay đổi khi triển khai: (1) classifier + tests; (2) storage/config migration + reclassify; (3) collector/worker integration; (4) UI/export; (5) fixtures đánh giá, tài liệu và packaging. Mỗi nhóm phải có checkpoint chạy được trước khi chuyển bước.
