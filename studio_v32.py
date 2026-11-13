
import os
import json
import time
import base64
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests
from openai import OpenAI
from PIL import Image

OUT = Path("output")
OUT.mkdir(exist_ok=True)

MODE = os.getenv("MODE", "plan")
CHANNEL = os.getenv("CHANNEL", "animals")
CUSTOM = os.getenv("CUSTOM_SCRIPT", "").strip()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
RUNWAY_KEY = os.getenv("RUNWAYML_API_SECRET", "")
YOUTUBE_KEY = os.getenv("YOUTUBE_API_KEY", "")

client = OpenAI()

CHANNELS = {
    "animals": {
        "name": "지구의 이웃들",
        "query": "funny cute animals cat dog shorts",
        "style": "귀여운 동물, 놀라운 행동, 코미디, 감동적 반전"
    },
    "philosophy": {
        "name": "퇴근 후 철학",
        "query": "life philosophy motivational shorts",
        "style": "시간의 유한함, 인생의 본질, 깊은 철학적 여운"
    },
    "nature": {
        "name": "초록 프레임",
        "query": "beautiful nature flowers garden shorts",
        "style": "아름다운 자연, 생명의 신비, 영화적 영상미"
    },
    "healing": {
        "name": "마음 한 스푼",
        "query": "emotional heartwarming life shorts",
        "style": "따뜻한 감성, 인간적인 이야기, 깊은 위로"
    },
    "beauty": {
        "name": "뷰티 꿀팁",
        "query": "viral makeup beauty transformation shorts",
        "style": "메이크업 변화, 실용적인 팁, 시각적 만족감"
    },
    "food": {
        "name": "냠냠 레시피",
        "query": "viral dessert drink recipe shorts",
        "style": "예쁜 디저트, 독특한 음료, 감각적인 음식 영상"
    }
}

CFG = CHANNELS.get(CHANNEL, CHANNELS["animals"])


def save_json(name, data):
    (OUT / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_json(name):
    return json.loads(
        (OUT / name).read_text(encoding="utf-8")
    )


def ask_ai(system, user):
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    )
    return json.loads(
        response.choices[0].message.content
    )


def youtube(endpoint, params):
    response = requests.get(
        "https://www.googleapis.com/youtube/v3/" + endpoint,
        params={**params, "key": YOUTUBE_KEY},
        timeout=60
    )
    response.raise_for_status()
    return response.json()


def find_trends():
    if not YOUTUBE_KEY:
        raise RuntimeError(
            "YOUTUBE_API_KEY is missing."
        )

    since = (
        datetime.now(timezone.utc) - timedelta(days=30)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    result = youtube("search", {
        "part": "snippet",
        "q": CFG["query"],
        "type": "video",
        "videoDuration": "short",
        "order": "viewCount",
        "publishedAfter": since,
        "maxResults": 25
    })

    ids = [
        item["id"]["videoId"]
        for item in result.get("items", [])
    ]

    if not ids:
        raise RuntimeError("No trend videos found.")

    details = youtube("videos", {
        "part": "snippet,statistics,contentDetails",
        "id": ",".join(ids)
    })

    trends = []

    for item in details.get("items", []):
        snippet = item["snippet"]
        stats = item.get("statistics", {})

        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))

        published = datetime.fromisoformat(
            snippet["publishedAt"].replace("Z", "+00:00")
        )

        days = max(
            1,
            (datetime.now(timezone.utc) - published)
            .total_seconds() / 86400
        )

        trends.append({
            "title": snippet["title"],
            "url": "https://www.youtube.com/watch?v=" + item["id"],
            "views": views,
            "likes": likes,
            "views_per_day": round(views / days),
            "published": snippet["publishedAt"],
            "duration": item["contentDetails"]["duration"]
        })

    trends.sort(
        key=lambda x: x["views_per_day"],
        reverse=True
    )

    save_json("trends.json", trends)
    return trends[:15]


WRITER = """
You are an elite Korean short-form video writer
and cinematic AI video director.

Create original 25-second vertical videos.
Never copy existing videos, characters, scripts
or copyrighted footage.

Use trend metadata only for broad inspiration.

Return JSON:
{
  "candidates": [
    {
      "title": "Korean title",
      "description": "Korean description",
      "hashtags": ["#tag"],
      "character": "Detailed consistent English character description",
      "visual_style": "English cinematic style",
      "scenes": [
        {
          "narration": "Short Korean narration",
          "caption": "Short Korean caption",
          "image": "Detailed English first-frame image prompt",
          "motion": "English physical motion and camera direction"
        }
      ]
    }
  ]
}

Rules:
- Exactly 5 scenes per candidate.
- Each scene lasts 5 seconds.
- Scene 1 starts with a striking action or mystery.
- Scene 2 raises a specific question.
- Scene 3 introduces an unexpected development.
- Scene 4 reveals the answer.
- Scene 5 delivers a memorable payoff.
- Narration must be short enough for 5 seconds.
- Captions maximum 16 Korean characters including spaces.
- Each scene must show a different meaningful action.
- No generic greetings or empty inspirational phrases.
- Preserve the same character and world across scenes.
- Image prompts describe one frozen starting frame.
- Motion prompts describe a feasible single action.
- No logos, text or watermarks in generated images.
- Keep image and motion prompts under 600 characters.
- For fictional animal stories, label the description
  as an AI-generated fictional story.
- Never invent factual claims or unsafe advice.
- If the user supplies a script, preserve its meaning.
"""


JUDGE = """
You are a strict short-form video editor.

Evaluate the provided candidate scripts independently.

Return JSON:
{
  "reviews": [
    {
      "index": 0,
      "hook": 0,
      "retention": 0,
      "originality": 0,
      "payoff": 0,
      "visual_feasibility": 0,
      "feedback": "Specific improvement in Korean"
    }
  ]
}

Each category is scored from 0 to 20.
Be strict. Do not inflate scores.
Reward specific action, curiosity, progression,
visual clarity, and a satisfying unexpected ending.
Penalize repetitive scenes, generic narration,
misleading claims, and physically impossible action.
"""


def validate_script(script):
    required = [
        "title", "description", "hashtags",
        "character", "visual_style", "scenes"
    ]

    for key in required:
        if key not in script:
            raise ValueError("Missing field: " + key)

    if len(script["scenes"]) != 5:
        raise ValueError("Exactly five scenes required.")

    for scene in script["scenes"]:
        for key in ["narration", "caption", "image", "motion"]:
            if not isinstance(scene.get(key), str):
                raise ValueError("Invalid scene: " + key)
            if not scene[key].strip():
                raise ValueError("Empty scene: " + key)

        if len(scene["caption"]) > 16:
            raise ValueError("Caption is too long.")

    return script


def make_plan():
    trends = find_trends()

    context = {
        "channel": CFG,
        "trends": trends,
        "user_script": CUSTOM,
        "instruction": "Generate exactly 3 original candidates."
    }

    candidates = ask_ai(
        WRITER,
        json.dumps(context, ensure_ascii=False)
    )["candidates"]

    if len(candidates) != 3:
        raise RuntimeError("Expected three candidates.")

    best = None
    best_score = -1
    history = []

    for attempt in range(3):
        reviews = ask_ai(
            JUDGE,
            json.dumps(candidates, ensure_ascii=False)
        )["reviews"]

        if len(reviews) != len(candidates):
            raise RuntimeError("Incomplete AI review.")

        ranked = []

        for review in reviews:
            score = sum(
                max(0, min(20, int(review[key])))
                for key in [
                    "hook", "retention", "originality",
                    "payoff", "visual_feasibility"
                ]
            )

            index = int(review["index"])

            if not 0 <= index < len(candidates):
                raise RuntimeError("Invalid review index.")

            ranked.append((score, index, review))

        ranked.sort(reverse=True, key=lambda x: x[0])

        score, index, review = ranked[0]
        winner = validate_script(candidates[index])

        history.append({
            "attempt": attempt + 1,
            "score": score,
            "review": review
        })

        if score > best_score:
            best = winner
            best_score = score

        if score >= 85:
            break

        if attempt < 2:
            revised = ask_ai(
                WRITER,
                json.dumps({
                    "instruction": "Rewrite this candidate. Return one candidate.",
                    "channel": CFG,
                    "user_script": CUSTOM,
                    "script": winner,
                    "feedback": review
                }, ensure_ascii=False)
            )
            candidates = revised["candidates"]

    best["quality_score"] = best_score
    best["quality_passed"] = best_score >= 85
    best["channel"] = CHANNEL
    best["review_history"] = history

    save_json("metadata.json", best)
    save_json("reviews.json", history)

    lines = [
        "# Shorts AI Studio 3.2",
        "",
        "## " + best["title"],
        "",
        "AI editorial score: " + str(best_score) + "/100",
        "",
        "Channel: " + CFG["name"],
        ""
    ]

    for i, scene in enumerate(best["scenes"], 1):
        lines += [
            "### Scene " + str(i),
            "",
            "Narration: " + scene["narration"],
            "",
            "Caption: " + scene["caption"],
            "",
            "Image: " + scene["image"],
            "",
            "Motion: " + scene["motion"],
            ""
        ]

    report = "\n".join(lines)

    (OUT / "plan.md").write_text(
        report, encoding="utf-8"
    )

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)

    print("Plan complete. Score:", best_score)


def runway_task(endpoint, payload):
    if not RUNWAY_KEY:
        raise RuntimeError("RUNWAYML_API_SECRET is missing.")

    headers = {
        "Authorization": "Bearer " + RUNWAY_KEY,
        "X-Runway-Version": "2024-11-06",
        "Content-Type": "application/json"
    }

    base = "https://api.dev.runwayml.com/v1"

    response = requests.post(
        base + "/" + endpoint,
        headers=headers,
        json=payload,
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(
            f"Runway request failed: {response.status_code} "
            + response.text[:1000]
        )

    task_id = response.json()["id"]
    print("Runway task:", task_id, flush=True)

    for _ in range(180):
        time.sleep(10)

        result = requests.get(
            base + "/tasks/" + task_id,
            headers=headers,
            timeout=60
        )

        result.raise_for_status()
        task = result.json()
        status = task["status"]

        print("Task status:", status, flush=True)

        if status == "SUCCEEDED":
            return task["output"][0]

        if status in ["FAILED", "CANCELLED"]:
            raise RuntimeError(
                "Runway generation failed: "
                + json.dumps(task, ensure_ascii=False)[:1500]
            )

    raise TimeoutError("Runway task timed out: " + task_id)


def download(url, path):
    with requests.get(
        url, stream=True, timeout=(30, 180)
    ) as response:
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_content(1024 * 1024):
                f.write(chunk)


def image_uri(path):
    with Image.open(path) as img:
        img.convert("RGB").save(
            OUT / "reference.jpg",
            quality=90
        )

    encoded = base64.b64encode(
        (OUT / "reference.jpg").read_bytes()
    ).decode("ascii")

    return "data:image/jpeg;base64," + encoded


def create_image(plan, index, reference=None):
    scene = plan["scenes"][index]

    prompt = (
        plan["character"] + ". "
        + plan["visual_style"] + ". "
        + scene["image"]
        + ". Vertical cinematic composition. "
        + "No text, no watermark."
    )

    payload = {
        "model": "gen4_image_turbo",
        "ratio": "720:1280",
        "promptText": prompt[:950]
    }

    if reference:
        payload["promptText"] = (
            "Use the same character as @hero. "
            + prompt
        )[:980]

        payload["referenceImages"] = [{
            "uri": image_uri(reference),
            "tag": "hero"
        }]

    
    payload.setdefault("referenceImages", [])

    url = runway_task("text_to_image", payload)


    path = OUT / f"scene_{index + 1}.jpg"
    download(url, path)

    # Normalize image format for later API requests.
    with Image.open(path) as img:
        rgb = img.convert("RGB")

    rgb.save(path, quality=95)
    return path


def preview():
    plan = validate_script(load_json("metadata.json"))

   
    if not plan.get("quality_passed"):
        print("Quality score below 85. Proceeding with user approval.")

    image = create_image(plan, 0)

    (OUT / "preview.jpg").write_bytes(
        image.read_bytes()
    )

    print("Preview created:", image)


def run_ffmpeg(*args):
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner",
         "-loglevel", "error", *map(str, args)],
        check=True
    )


def media_duration(path):
    result = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ])
    return float(result)


def make_voice(text, path):
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="coral",
        input=text,
        instructions=(
            "Speak in natural Korean. "
            "Engaging storytelling, clear pronunciation, "
            "short and expressive."
        )
    ) as response:
        response.stream_to_file(path)


def write_ass(caption, index, duration, path):
    # Prevent special ASS control sequences.
    caption = caption.replace("\\", "")
    caption = caption.replace("{", "").replace("}", "")
    caption = caption.replace("\n", " ")

    end = f"0:00:{duration:05.2f}"

    color = (
        "&H0000D7FF" if index == 0
        else "&H00FFFFFF"
    )

    content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Noto Sans CJK KR,78,{color},&H000000FF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,80,80,360,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{end},Main,,0,0,0,,{caption}
"""

    path.write_text(content, encoding="utf-8")


def render():
    plan = validate_script(load_json("metadata.json"))

    if plan.get("channel") != CHANNEL:
        raise RuntimeError("Approved plan channel mismatch.")

    if not plan.get("quality_passed"):
        raise RuntimeError("Plan did not pass quality review.")

    first = OUT / "preview.jpg"

    if not first.exists():
        raise RuntimeError(
            "Approved preview.jpg is required. "
            "Run preview mode first."
        )

    clips = []

    for i, scene in enumerate(plan["scenes"]):
        print("Rendering scene", i + 1, flush=True)

        image = first if i == 0 else create_image(
            plan, i, reference=first
        )

        video_url = runway_task("image_to_video", {
            "model": "gen4_turbo",
            "promptImage": image_uri(image),
            "promptText": scene["motion"][:950],
            "ratio": "720:1280",
            "duration": 5
        })

        raw = OUT / f"raw_{i + 1}.mp4"
        download(video_url, raw)

        voice = OUT / f"voice_{i + 1}.mp3"
        make_voice(scene["narration"], voice)

        voice_seconds = media_duration(voice)
        speed = max(1.0, voice_seconds / 4.7)

        if speed > 2:
            raise RuntimeError(
                "Narration too long for scene "
                + str(i + 1)
            )

        subtitle = OUT / f"caption_{i + 1}.ass"
        write_ass(scene["caption"], i, 5, subtitle)

        clip = OUT / f"clip_{i + 1}.mp4"

        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "setsar=1,fps=30,"
            f"ass={subtitle.as_posix()}"
        )

        run_ffmpeg(
            "-i", raw,
            "-i", voice,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", vf,
            "-af", f"atempo={speed:.4f},apad",
            "-t", "5",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "19",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-ac", "2",
            clip
        )

        clips.append(clip)

    concat = OUT / "concat.txt"

    concat.write_text(
        "\n".join(
            f"file '{p.resolve().as_posix()}'"
            for p in clips
        ),
        encoding="utf-8"
    )

    final = OUT / "shorts_final.mp4"

    run_ffmpeg(
        "-f", "concat",
        "-safe", "0",
        "-i", concat,
        "-c", "copy",
        "-movflags", "+faststart",
        final
    )

    duration = media_duration(final)

    if duration < 24 or duration > 26:
        raise RuntimeError(
            f"Unexpected video duration: {duration}"
        )

    print("Final video created:", final)
    print("Duration:", duration)


if __name__ == "__main__":
    if MODE == "plan":
        make_plan()
    elif MODE == "preview":
        preview()
    elif MODE == "render":
        render()
    else:
        raise ValueError("Unknown mode: " + MODE)
