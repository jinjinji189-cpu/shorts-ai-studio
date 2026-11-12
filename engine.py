
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
    "요리·디저트": "viral dessert recipe",
    "뷰티": "viral makeup tutorial",
    "동물·자연": "amazing animals nature",
    "생활 꿀팁": "creative life hacks",
    "철학·명언": "life philosophy motivation",
    "중국 인기 콘텐츠": "China trending food culture",
    "여행·문화": "amazing travel culture"
}

OUTPUT = Path("docs")
OUTPUT.mkdir(exist_ok=True)
HISTORY = OUTPUT / "history.json"

seen = set()

if HISTORY.exists():
    seen = set(json.loads(
        HISTORY.read_text(encoding="utf-8")
    ))

def youtube_api(endpoint, params):
    params["key"] = API_KEY
    url = (
        "https://www.googleapis.com/youtube/v3/"
        + endpoint + "?"
        + urllib.parse.urlencode(params)
    )
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)

results = []
today = datetime.now(timezone.utc)

published_after = (
    today - timedelta(days=365)
).strftime("%Y-%m-%dT%H:%M:%SZ")

for category, keyword in KEYWORDS.items():

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
        "id": ",".join(ids)
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

        results.append({
            "category": category,
            "title": snippet["title"],
            "channel": snippet["channelTitle"],
            "views": views,
            "url": "https://www.youtube.com/watch?v="
                   + video_id,
            "license": "CC 표시 / 권리 검토 필요",
            "status": "검토 대기"
        })

results.sort(
    key=lambda x: x["views"],
    reverse=True
)

HISTORY.write_text(
    json.dumps(list(seen), ensure_ascii=False),
    encoding="utf-8"
)

(OUTPUT / "videos.json").write_text(
    json.dumps(
        results,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

rows = ""

for item in results:
    title = html.escape(item["title"])
    channel = html.escape(item["channel"])
    category = html.escape(item["category"])
    url = html.escape(item["url"])

    rows += f"""
    <div class="card">
      <small>{category}</small>
      <h3>{title}</h3>
      <p>채널: {channel}</p>
      <p>조회수: {item['views']:,}회</p>
      <p>CC 표시 · 권리 검토 필요</p>
      <a href="{url}" target="_blank">
        원본 영상 보기
      </a>
    </div>
    """

page = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport"
 content="width=device-width, initial-scale=1">
<title>쇼츠 AI 스튜디오</title>
<style>
body {{
 font-family: sans-serif;
 background: #f4f6f9;
 color: #222;
 margin: 20px;
}}
.card {{
 background: white;
 padding: 18px;
 margin-bottom: 15px;
 border-radius: 12px;
}}
small {{ color: #2563eb; }}
a {{
 display: inline-block;
 background: #2563eb;
 color: white;
 padding: 10px 16px;
 border-radius: 8px;
 text-decoration: none;
}}
</style>
</head>
<body>
<h1>쇼츠 AI 스튜디오</h1>
<p>해외 인기 영상 자동 발굴</p>
<p>오늘 발견: {len(results)}개</p>
<p>조회수 100만 이상 / CC 후보</p>
<p>저작권 최종 확인 후 사용하세요.</p>
{rows}
</body>
</html>
"""

(OUTPUT / "index.html").write_text(
    page,
    encoding="utf-8"
)

print(f"검색 완료: {len(results)}개 발견")
