
# ==========================================
# 쇼츠 AI 스튜디오 5.0
# 자동 영상 편집 엔진
# ==========================================

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def run_command(command):
    print("실행:", " ".join(map(str, command)))
    subprocess.run(command, check=True)


def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg가 설치되어 있지 않습니다."
        )

    if not shutil.which("ffprobe"):
        raise RuntimeError(
            "FFprobe가 설치되어 있지 않습니다."
        )


def get_duration(video_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return float(result.stdout.strip())


def get_font():
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/malgun.ttf",
    ]

    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    return None


def make_srt(text, duration, output_path):
    sentences = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not sentences:
        return False

    seconds_per_line = duration / len(sentences)

    def timestamp(seconds):
        milliseconds = round(seconds * 1000)

        hours, remainder = divmod(
            milliseconds, 3600000
        )

        minutes, remainder = divmod(
            remainder, 60000
        )

        secs, millis = divmod(
            remainder, 1000
        )

        return (
            f"{hours:02}:{minutes:02}:"
            f"{secs:02},{millis:03}"
        )

    blocks = []

    for index, sentence in enumerate(sentences):
        start = index * seconds_per_line
        end = min(
            duration,
            (index + 1) * seconds_per_line
        )

        blocks.append(
            f"{index + 1}\n"
            f"{timestamp(start)} --> {timestamp(end)}\n"
            f"{sentence}\n"
        )

    output_path.write_text(
        "\n".join(blocks),
        encoding="utf-8-sig"
    )

    return True


def make_shorts(
    input_video,
    output_video,
    duration=30,
    narration=None,
    music=None,
    subtitle_text=None,
):

    check_ffmpeg()

    input_video = Path(input_video)
    output_video = Path(output_video)

    if not input_video.exists():
        raise FileNotFoundError(
            f"원본 영상을 찾을 수 없습니다: {input_video}"
        )

    output_video.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    source_duration = get_duration(input_video)

    if source_duration < duration:
        print(
            "원본 영상이 짧아 마지막 장면을 반복합니다."
        )

    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)

        subtitle_path = temp_path / "captions.srt"

        filters = [
            (
                "[0:v]"
                "scale=1080:1920:"
                "force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                "setsar=1,"
                "fps=30,"
                "format=yuv420p"
                "[video]"
            )
        ]

        command = [
            "ffmpeg",
            "-y",
            "-stream_loop", "-1",
            "-i", str(input_video),
        ]

        audio_inputs = []

        if narration:
            narration = Path(narration)

            if not narration.exists():
                raise FileNotFoundError(
                    f"내레이션 파일 없음: {narration}"
                )

            command += [
                "-i", str(narration)
            ]

            audio_inputs.append(
                ("narration", len(audio_inputs) + 1)
            )

        if music:
            music = Path(music)

            if not music.exists():
                raise FileNotFoundError(
                    f"배경음악 파일 없음: {music}"
                )

            command += [
                "-stream_loop", "-1",
                "-i", str(music)
            ]

            audio_inputs.append(
                ("music", len(audio_inputs) + 1)
            )

        if subtitle_text:
            subtitle_path.write_text(
                subtitle_text,
                encoding="utf-8"
            )

            srt_path = temp_path / "captions.srt"

            make_srt(
                subtitle_text,
                duration,
                srt_path
            )

            font = get_font()

            subtitle_filter = (
                "subtitles="
                + str(srt_path).replace("\\", "/")
                + ":force_style="
                + "'FontName=NanumGothic,"
                + "FontSize=18,"
                + "PrimaryColour=&H00FFFFFF,"
                + "OutlineColour=&H00000000,"
                + "BorderStyle=1,"
                + "Outline=2,"
                + "Alignment=2,"
                + "MarginV=160'"
            )

            if font:
                subtitle_filter += (
                    ":fontsdir="
                    + str(Path(font).parent).replace("\\", "/")
                )

            filters[0] = filters[0].replace(
                "[video]",
                "," + subtitle_filter + "[video]"
            )

        audio_filters = []
        audio_labels = []

        for kind, input_index in audio_inputs:
            if kind == "narration":
                audio_filters.append(
                    f"[{input_index}:a]"
                    "volume=1.0,"
                    "aresample=async=1"
                    "[voice]"
                )
                audio_labels.append("[voice]")

            elif kind == "music":
                audio_filters.append(
                    f"[{input_index}:a]"
                    "volume=0.12,"
                    "aresample=async=1"
                    "[bgm]"
                )
                audio_labels.append("[bgm]")

        filters.extend(audio_filters)

        if len(audio_labels) == 2:
            filters.append(
                "[voice][bgm]"
                "amix=inputs=2:"
                "duration=first:"
                "dropout_transition=2"
                "[audio]"
            )

            audio_map = "[audio]"

        elif len(audio_labels) == 1:
            audio_map = audio_labels[0]

        else:
            audio_map = None

        command += [
            "-filter_complex",
            ";".join(filters),
            "-map", "[video]",
        ]

        if audio_map:
            command += [
                "-map", audio_map
            ]
        else:
            command += ["-an"]

        command += [
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-movflags", "+faststart",
        ]

        if audio_map:
            command += [
                "-c:a", "aac",
                "-b:a", "160k",
                "-ar", "44100",
            ]

        command.append(str(output_video))

        run_command(command)

    print()
    print("영상 제작 완료!")
    print("저장 위치:", output_video)


def main():
    parser = argparse.ArgumentParser(
        description="쇼츠 AI 스튜디오 5.0 영상 편집"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="원본 MP4 파일"
    )

    parser.add_argument(
        "--output",
        default="shorts_final.mp4",
        help="완성 영상 저장 경로"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        choices=[30, 45, 60],
        help="영상 길이"
    )

    parser.add_argument(
        "--narration",
        help="한국어 내레이션 MP3"
    )

    parser.add_argument(
        "--music",
        help="배경음악 MP3"
    )

    parser.add_argument(
        "--subtitles",
        help="한국어 자막 TXT 파일"
    )

    args = parser.parse_args()

    subtitle_text = None

    if args.subtitles:
        subtitle_text = Path(
            args.subtitles
        ).read_text(encoding="utf-8")

    make_shorts(
        input_video=args.input,
        output_video=args.output,
        duration=args.duration,
        narration=args.narration,
        music=args.music,
        subtitle_text=subtitle_text,
    )


if __name__ == "__main__":
    main()
