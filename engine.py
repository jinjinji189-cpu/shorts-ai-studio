
import os
import json
import html
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("YOUTUBE_API_KEY")

if not API_KEY:
    raise RuntimeError("YOUTUBE_API_KEY 설정이 필요합니다.")

KEYWORDS = {
    "요리·디저트": [
        "viral dessert recipe",
        "amazing street food"
    ],
    "뷰티": [
        "viral makeup tutorial",
        "beauty transformation"
    ],
    "동물·자연": [
        "amazing animals nature",
        "funny cute animals"
    ],
    "생활 꿀팁": [
        "creative life hacks",
        "amazing useful inventions"
    ],
    "철학·명언": [
        "life philosophy motivation",
        "powerful life lessons"
    ],
    "중국 인기 콘텐츠": [
        "China trending food culture",
        "Chinese amazing skills"
    ],
    "여행·문화": [
        "amazing travel culture",
        "beautiful places world"
    ]
}

OUTPUT = Path("docs")
OUTPUT.mkdir(exist_ok=True)

HISTORY = OUTPUT / "history.json"
ARCHIVE = OUTPUT / "archive.json"
VIDEOS = OUTPUT / "videos.json"

def load_json(path, default):
    if path.exists():
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    return default

def save_json(path, data):
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

seen = set(load_json(HISTORY, []))
archive = load_json(ARCHIVE, [])

if not archive:
    archive = load_json(VIDEOS, [])

for item in archive:
    if "id" not in item:
        item["id"] = item["url"].split("v=")[-1]
    seen.add(item["id"])

def youtube_api(endpoint, params):
    params["key"] = API_KEY
    url = (
        "https://www.googleapis.com/youtube/v3/"
        + endpoint + "?"
        + urllib.parse.urlencode(params)
    )

    with urllib.request.urlopen(
        url, timeout=30
    ) as response:
        return json.load(response)

today = datetime.now(timezone.utc)

kst = today.astimezone(
    timezone(timedelta(hours=9))
)

date_text = kst.strftime("%Y-%m-%d")

published_after = (
    today - timedelta(days=365)
).strftime("%Y-%m-%dT%H:%M:%SZ")

results = []

for category, keywords in KEYWORDS.items():

    for keyword in keywords:

        if len(results) >= 30:
            break

        data = youtube_api("search", {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "order": "viewCount",
            "videoLicense": "creativeCommon",
            "publishedAfter": published_after,
            "maxResults": 50
        })

        ids = [
            item["id"]["videoId"]
            for item in data.get("items", [])
        ]

        if not ids:
            continue

        videos = youtube_api("videos", {
            "part": "snippet,statistics,status",
            "id": ",".join(ids),
            "hl": "ko"
        })

        for video in videos.get("items", []):

            video_id = video["id"]

            views = int(
                video.get("statistics", {})
                .get("viewCount", 0)
            )

            license_type = video.get(
                "status", {}
            ).get("license", "")

            if views < 1000000:
                continue

            if license_type != "creativeCommon":
                continue

            if video_id in seen:
                continue

            if len(results) >= 30:
                break

            seen.add(video_id)

            snippet = video["snippet"]

            localized = snippet.get(
                "localized", {}
            ).get("title", snippet["title"])

            results.append({
                "id": video_id,
                "category": category,
                "title": snippet["title"],
                "localized_title": localized,
                "channel": snippet["channelTitle"],
                "views": views,
                "url": (
                    "https://www.youtube.com/watch?v="
                    + video_id
                ),
                "license": "CC 표시 / 권리 검토 필요",
                "status": "검토 대기",
                "date": date_text
            })

results.sort(
    key=lambda x: x["views"],
    reverse=True
)

archive = results + archive

save_json(HISTORY, sorted(seen))
save_json(VIDEOS, results)
save_json(ARCHIVE, archive)

rows = ""

for item in archive:

    title = html.escape(
        item.get("localized_title", item["title"])
    )

    original = html.escape(item["title"])
    channel = html.escape(item["channel"])
    category = html.escape(item["category"])
    url = html.escape(item["url"], quote=True)
    vid = html.escape(item["id"], quote=True)
    found = html.escape(item.get("date", "이전 검색"))

    rows += f"""
    <div class="card"
         data-category="{category}"
         data-id="{vid}">

      <small>{category} · {found}</small>

      <img class="thumb"
       src="https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
       loading="lazy" alt="영상 미리보기">

      <h3>{title}</h3>

      <details>
        <summary>원본 제목</summary>
        <p>{original}</p>
      </details>

      <p>채널: {channel}</p>
      <p>조회수: {item['views']:,}회</p>

      <span class="license">
        CC 표시 · 권리 검토 필요
      </span>

      <p>
        <a href="{url}" target="_blank"
           rel="noopener noreferrer">
          원본 영상 및 권리 확인
        </a>
      </p>

      <label class="check">
        <input type="checkbox"
         class="rights">
        재편집·번역·상업적 이용 권한 확인
      </label>

      <label class="check">
        <input type="checkbox"
         class="music">
        음악·이미지 등 제3자 권리 확인
      </label>

      <button class="approve"
        onclick="approve(this)">
        제작 대기 목록에 추가
      </button>

      <p class="state"></p>
    </div>
    """

page = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport"
 content="width=device-width, initial-scale=1">
<title>쇼츠 AI 스튜디오 2.0</title>
<style>
body {{
 font-family: sans-serif;
 background: #f4f6f9;
 color: #222;
 margin: 16px;
}}
main {{
 max-width: 850px;
 margin: auto;
}}
header {{
 background: #172554;
 color: white;
 padding: 22px;
 border-radius: 18px;
 margin-bottom: 16px;
}}
.stats {{
 display: grid;
 grid-template-columns: repeat(3, 1fr);
 gap: 8px;
}}
.stat {{
 background: white;
 color: #172554;
 border-radius: 10px;
 padding: 12px 6px;
 text-align: center;
 font-size: 13px;
}}
.stat b {{
 display: block;
 font-size: 24px;
}}
.card {{
 background: white;
 padding: 18px;
 margin-bottom: 15px;
 border-radius: 14px;
}}
.thumb {{
 width: 100%;
 border-radius: 10px;
 margin-top: 12px;
}}
small {{ color: #2563eb; }}
a, button {{
 display: inline-block;
 background: #2563eb;
 color: white;
 padding: 12px 16px;
 border-radius: 8px;
 border: none;
 text-decoration: none;
 font-size: 15px;
 cursor: pointer;
}}
button.approve {{
 width: 100%;
 background: #166534;
 margin-top: 14px;
}}
.check {{
 display: block;
 padding: 9px 0;
 font-size: 14px;
}}
.license {{
 background: #fef3c7;
 padding: 7px;
 border-radius: 6px;
 font-size: 13px;
}}
select {{
 width: 100%;
 padding: 12px;
 border: 1px solid #ddd;
 border-radius: 8px;
 margin-bottom: 14px;
 font-size: 16px;
}}
.state {{ color: #166534; }}
</style>
</head>
<body>
<main>
<header>
<h1>쇼츠 AI 스튜디오 2.0</h1>
<p>해외 인기 콘텐츠 제작 관리</p>

<div class="stats">
 <div class="stat">
  <b>{len(results)}</b>오늘 발견
 </div>
 <div class="stat">
  <b>{len(archive)}</b>누적 영상
 </div>
 <div class="stat">
  <b id="queueCount">0</b>제작 대기
 </div>
</div>
<p>업데이트: {date_text}</p>
</header>

<p>조회수 100만 이상 · CC 후보</p>
<p>저작권 최종 확인 후 사용하세요.</p>

<select id="filter" onchange="filterCards()">
 <option value="all">전체 영상</option>
 <option value="요리·디저트">요리·디저트</option>
 <option value="뷰티">뷰티</option>
 <option value="동물·자연">동물·자연</option>
 <option value="생활 꿀팁">생활 꿀팁</option>
 <option value="철학·명언">철학·명언</option>
 <option value="중국 인기 콘텐츠">중국 인기 콘텐츠</option>
 <option value="여행·문화">여행·문화</option>
 <option value="approved">제작 대기 영상</option>
</select>

{rows}

</main>

<script>
let queue = [];

try {{
 queue = JSON.parse(
  localStorage.getItem("shortsQueue") || "[]"
 );
}} catch(e) {{
 queue = [];
}}

function refresh() {{
 document.getElementById("queueCount")
 .textContent = queue.length;

 document.querySelectorAll(".card")
 .forEach(card => {{
  let approved = queue.includes(card.dataset.id);
  card.querySelector(".state").textContent =
   approved ? "제작 대기 등록됨 (이 기기)" : "";

  card.querySelector(".approve").textContent =
   approved ? "제작 대기 취소" :
   "제작 대기 목록에 추가";

  if(approved) {{
   card.querySelector(".rights").checked = true;
   card.querySelector(".music").checked = true;
  }}
 }});
}}

function approve(button) {{
 const card = button.closest(".card");
 const id = card.dataset.id;

 if(queue.includes(id)) {{
  queue = queue.filter(v => v !== id);
 }} else {{
  if(!card.querySelector(".rights").checked ||
     !card.querySelector(".music").checked) {{
   alert("저작권 확인 항목 두 개를 먼저 체크하세요.");
   return;
  }}
  queue.push(id);
 }}

 localStorage.setItem(
  "shortsQueue", JSON.stringify(queue)
 );

 refresh();
 filterCards();
}}

function filterCards() {{
 const value = document.getElementById("filter").value;

 document.querySelectorAll(".card")
 .forEach(card => {{
  const show =
   value === "all" ||
   value === card.dataset.category ||
   (value === "approved" &&
    queue.includes(card.dataset.id));

  card.style.display = show ? "" : "none";
 }});
}}

refresh();
</script>
</body>
</html>
"""

(OUTPUT / "index.html").write_text(
    page,
    encoding="utf-8"
)

print(f"검색 완료: {len(results)}개 발견")
print(f"누적 영상: {len(archive)}개")



# ==========================================
# 쇼츠 AI 스튜디오 3.0 - 모바일 승인 기능
# ==========================================

approval_code = """
<style>
.approval-panel {
    background: white;
    padding: 18px;
    border-radius: 14px;
    margin: 18px 0;
}
.approval-stats {
    display: flex;
    gap: 10px;
    margin: 12px 0;
}
.approval-stat {
    flex: 1;
    background: #f1f5f9;
    padding: 12px;
    border-radius: 10px;
    text-align: center;
}
.approval-stat strong {
    display: block;
    font-size: 26px;
}
.video-thumb {
    width: 100%;
    border-radius: 10px;
    margin: 10px 0;
}
.approval-buttons {
    display: flex;
    gap: 6px;
    margin-top: 12px;
    flex-wrap: wrap;
}
.approval-buttons button {
    flex: 1;
    padding: 12px 8px;
    border: 0;
    border-radius: 8px;
    font-size: 14px;
    cursor: pointer;
}
.approve-btn {
    background: #16a34a;
    color: white;
}
.hold-btn {
    background: #f59e0b;
    color: white;
}
.reject-btn {
    background: #ef4444;
    color: white;
}
.video-status {
    padding: 8px;
    background: #f1f5f9;
    border-radius: 8px;
    margin-top: 10px;
}
.korean-title {
    width: 100%;
    box-sizing: border-box;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 8px;
    margin-top: 10px;
}
#approval-filter {
    width: 100%;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid #ddd;
}
</style>

<script>
document.addEventListener("DOMContentLoaded", function () {

    const storageKey = "shorts_studio_approvals_v3";
    let saved = {};

    try {
        saved = JSON.parse(
            localStorage.getItem(storageKey) || "{}"
        );
    } catch (e) {
        saved = {};
    }

    const cards = Array.from(
        document.querySelectorAll(".card")
    );

    const panel = document.createElement("div");
    panel.className = "approval-panel";

    panel.innerHTML = `
        <h2>나의 제작 관리</h2>
        <div class="approval-stats">
            <div class="approval-stat">
                <strong id="total-count">0</strong>
                전체
            </div>
            <div class="approval-stat">
                <strong id="approved-count">0</strong>
                승인
            </div>
            <div class="approval-stat">
                <strong id="hold-count">0</strong>
                보류
            </div>
        </div>

        <select id="approval-filter">
            <option value="all">전체 영상 보기</option>
            <option value="검토 대기">검토 대기</option>
            <option value="제작 승인">제작 승인</option>
            <option value="보류">보류 영상</option>
            <option value="제외">제외 영상</option>
        </select>

        <p style="font-size:12px;color:#64748b">
            승인 정보는 현재 브라우저에 저장됩니다.
        </p>
    `;

    const heading = document.querySelector("h1");

    if (heading) {
        heading.after(panel);
    } else {
        document.body.prepend(panel);
    }

    function saveData() {
        try {
            localStorage.setItem(
                storageKey,
                JSON.stringify(saved)
            );
            return true;
        } catch (e) {
            alert("저장할 수 없습니다. 브라우저 설정을 확인하세요.");
            return false;
        }
    }

    function updateCounts() {

        const ids = cards
            .map(c => c.dataset.videoId)
            .filter(Boolean);

        document.getElementById("total-count")
            .textContent = ids.length;

        document.getElementById("approved-count")
            .textContent = ids.filter(
                id => saved[id]?.status === "제작 승인"
            ).length;

        document.getElementById("hold-count")
            .textContent = ids.filter(
                id => saved[id]?.status === "보류"
            ).length;
    }

    function applyFilter() {

        const filter = document.getElementById(
            "approval-filter"
        ).value;

        cards.forEach(card => {

            const id = card.dataset.videoId;

            const status =
                saved[id]?.status || "검토 대기";

            card.style.display =
                filter === "all" || filter === status
                ? ""
                : "none";
        });
    }

    cards.forEach(card => {

        const link = card.querySelector(
            'a[href*="youtube.com/watch"]'
        );

        if (!link) return;

        const url = new URL(link.href);
        const id = url.searchParams.get("v");

        if (!id || !/^[a-zA-Z0-9_-]{11}$/.test(id)) return;

        card.dataset.videoId = id;

        if (!saved[id]) {
            saved[id] = {
                status: "검토 대기",
                koreanTitle: ""
            };
        }

        const img = document.createElement("img");

        img.className = "video-thumb";
        img.loading = "lazy";
        img.alt = "영상 썸네일";
        img.src =
            "https://i.ytimg.com/vi/" +
            id + "/hqdefault.jpg";

        card.prepend(img);

        const titleInput = document.createElement("input");

        titleInput.className = "korean-title";
        titleInput.placeholder = "한국어 제작 제목 입력";
        titleInput.value = saved[id].koreanTitle || "";

        titleInput.addEventListener("change", function () {
            saved[id].koreanTitle = this.value;
            saveData();
        });

        card.appendChild(titleInput);

        const statusBox = document.createElement("div");
        statusBox.className = "video-status";
        statusBox.textContent =
            "현재 상태: " + saved[id].status;

        card.appendChild(statusBox);

        const buttons = document.createElement("div");
        buttons.className = "approval-buttons";

        const options = [
            ["제작 승인", "approve-btn"],
            ["보류", "hold-btn"],
            ["제외", "reject-btn"]
        ];

        options.forEach(function(option) {

            const button = document.createElement("button");

            button.textContent = option[0];
            button.className = option[1];

            button.addEventListener("click", function() {

                if (option[0] === "제작 승인") {

                    const confirmed = confirm(
                        "원본 영상의 재편집 권한과 음악 등 제3자 권리를 확인하셨나요?"
                    );

                    if (!confirmed) return;
                }

                const previous = saved[id].status;
                saved[id].status = option[0];

                if (!saveData()) {
                    saved[id].status = previous;
                    return;
                }

                statusBox.textContent =
                    "현재 상태: " + option[0];

                updateCounts();
                applyFilter();
            });

            buttons.appendChild(button);
        });

        card.appendChild(buttons);
    });

    document.getElementById(
        "approval-filter"
    ).addEventListener("change", applyFilter);

    updateCounts();
});
</script>
"""

dashboard_path = Path("docs/index.html")

if dashboard_path.exists():
    dashboard_html = dashboard_path.read_text(
        encoding="utf-8"
    )

    dashboard_html = dashboard_html.replace(
        "</body>",
        approval_code + "</body>",
        1
    )

    dashboard_path.write_text(
        dashboard_html,
        encoding="utf-8"
    )

    print("쇼츠 AI 스튜디오 3.0 승인 기능 추가 완료")



# ==========================================
# 쇼츠 AI 스튜디오 3.1 - 디자인 및 승인 개선
# ==========================================

upgrade_code = """
<style>
.approval-panel {
    background: #ffffff !important;
    color: #172554 !important;
    padding: 20px !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}

.approval-panel h2 {
    color: #172554 !important;
    font-size: 22px;
    margin-top: 0;
    margin-bottom: 18px;
}

.approval-stat {
    background: #eef2ff !important;
    color: #172554 !important;
}

.approval-stat strong {
    color: #2563eb !important;
    font-size: 28px;
}

#approval-filter {
    background: #ffffff !important;
    color: #172554 !important;
    font-size: 16px;
    border: 1px solid #cbd5e1;
}

.video-status {
    color: #334155 !important;
    background: #f1f5f9 !important;
    font-weight: 600;
}

.approval-buttons button {
    min-height: 48px;
    font-weight: 600;
}

.korean-title {
    font-size: 16px;
    min-height: 44px;
    color: #222222 !important;
    background: #ffffff !important;
}

.video-thumb {
    max-height: 320px;
    object-fit: contain;
    background: #f1f5f9;
}

@media (max-width: 600px) {
    .approval-panel {
        padding: 14px !important;
    }

    .approval-stats {
        gap: 6px;
    }

    .approval-stat {
        padding: 10px 5px;
        font-size: 13px;
    }

    .approval-stat strong {
        font-size: 24px;
    }
}
</style>

<script>
document.addEventListener("DOMContentLoaded", function () {

    document.title = "쇼츠 AI 스튜디오 3.1";

    const heading = document.querySelector("h1");

    if (heading) {
        heading.textContent = "쇼츠 AI 스튜디오 3.1";
    }

    const panel = document.querySelector(".approval-panel");

    if (panel) {
        const title = panel.querySelector("h2");

        if (title) {
            title.textContent = "나의 제작 관리";
        }
    }

    document.querySelectorAll(".card").forEach(function(card) {

        const approveButton = card.querySelector(".approve-btn");

        if (!approveButton) return;

        approveButton.addEventListener("click", function(event) {

            const checks = Array.from(
                card.querySelectorAll('input[type="checkbox"]')
            );

            if (
                checks.length < 2 ||
                !checks.every(check => check.checked)
            ) {
                event.preventDefault();
                event.stopImmediatePropagation();

                alert(
                    "원본 영상의 재편집 권한과 음악 등 제3자 권리를 먼저 확인하고 체크해 주세요."
                );

                return;
            }

        }, true);

    });

});
</script>
"""

dashboard_path = Path("docs/index.html")

if dashboard_path.exists():

    dashboard_html = dashboard_path.read_text(
        encoding="utf-8"
    )

    dashboard_html = dashboard_html.replace(
        "</body>",
        upgrade_code + "</body>",
        1
    )

    dashboard_path.write_text(
        dashboard_html,
        encoding="utf-8"
    )

    print("쇼츠 AI 스튜디오 3.1 업그레이드 완료")
