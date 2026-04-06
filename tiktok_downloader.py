from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class TikTokDownloadError(Exception):
    """Raised when parsing or downloading TikTok video fails."""


@dataclass
class VideoInfo:
    video_id: str
    description: str
    download_url: str


class TikTokDownloader:
    def __init__(self, timeout: int = 20):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.timeout = timeout

    def _normalize_url(self, url: str) -> str:
        if not url:
            raise TikTokDownloadError("链接不能为空。")

        url = url.strip()
        if not urlparse(url).scheme:
            url = f"https://{url}"

        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            return response.url
        except requests.RequestException as exc:
            raise TikTokDownloadError(f"无法访问链接：{exc}") from exc

    def _extract_json_blob(self, html: str) -> dict:
        # 新版网页通常在这个 script 标签中。
        m = re.search(
            r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
            html,
            re.S,
        )
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError as exc:
                raise TikTokDownloadError("页面数据解析失败（JSON 无法解析）。") from exc

        raise TikTokDownloadError("未在页面中找到视频数据，可能链接无效或受地区限制。")

    def _find_item_struct(self, data: dict) -> dict:
        default_scope = data.get("__DEFAULT_SCOPE__", {})

        # 常见路径1：webapp.video-detail
        vd = default_scope.get("webapp.video-detail", {}).get("itemInfo", {}).get("itemStruct")
        if vd:
            return vd

        # 常见路径2：webapp.video-detail 的其它键名兼容
        for key, value in default_scope.items():
            if "video-detail" in key and isinstance(value, dict):
                item_struct = value.get("itemInfo", {}).get("itemStruct")
                if item_struct:
                    return item_struct

        raise TikTokDownloadError("未能从页面中提取视频结构数据。")

    @staticmethod
    def _build_no_watermark_url(url: str) -> str:
        # 经典无水印处理：playwm -> play
        return (
            url.replace("playwm", "play")
            .replace("watermark=1", "watermark=0")
            .replace("is_play_url=1", "is_play_url=0")
        )

    def get_video_info(self, url: str) -> VideoInfo:
        final_url = self._normalize_url(url)

        try:
            page = self.session.get(final_url, timeout=self.timeout)
            page.raise_for_status()
        except requests.RequestException as exc:
            raise TikTokDownloadError(f"打开视频页面失败：{exc}") from exc

        data = self._extract_json_blob(page.text)
        item = self._find_item_struct(data)

        video_id = item.get("id") or "tiktok_video"
        desc = (item.get("desc") or "tiktok_video").strip()

        video_block = item.get("video") or {}
        raw_url = (
            video_block.get("downloadAddr")
            or video_block.get("playAddr")
            or video_block.get("download_addr")
            or ""
        )
        if not raw_url:
            raise TikTokDownloadError("未找到视频下载地址。")

        no_wm_url = self._build_no_watermark_url(raw_url)
        return VideoInfo(video_id=video_id, description=desc, download_url=no_wm_url)

    @staticmethod
    def _safe_filename(name: str, max_len: int = 80) -> str:
        name = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", name).strip(" .")
        if not name:
            name = "tiktok_video"
        return name[:max_len]

    def download(self, info: VideoInfo, output_dir: str | Path) -> Path:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        file_name = self._safe_filename(info.description)
        target_file = output_path / f"{file_name}_{info.video_id}.mp4"

        try:
            with self.session.get(info.download_url, stream=True, timeout=self.timeout) as resp:
                resp.raise_for_status()
                with open(target_file, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 128):
                        if chunk:
                            f.write(chunk)
        except requests.RequestException as exc:
            raise TikTokDownloadError(f"下载失败：{exc}") from exc

        if target_file.stat().st_size == 0:
            raise TikTokDownloadError("下载结果为空文件。")

        return target_file


def download_tiktok_video(url: str, output_dir: str | Path) -> Path:
    downloader = TikTokDownloader()
    info = downloader.get_video_info(url)
    return downloader.download(info, output_dir)
