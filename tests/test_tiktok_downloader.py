import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from tiktok_downloader import TikTokDownloadError, TikTokDownloader, VideoInfo


class TestTikTokDownloader(unittest.TestCase):
    def setUp(self) -> None:
        self.downloader = TikTokDownloader(timeout=1)

    def test_build_no_watermark_url(self) -> None:
        raw = "https://example.com/playwm/video.mp4?watermark=1&is_play_url=1"
        got = self.downloader._build_no_watermark_url(raw)
        self.assertIn("play/video.mp4", got)
        self.assertIn("watermark=0", got)
        self.assertIn("is_play_url=0", got)

    def test_extract_json_blob_success(self) -> None:
        html = """
        <html><body>
        <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">
        {"__DEFAULT_SCOPE__":{"webapp.video-detail":{"itemInfo":{"itemStruct":{"id":"1"}}}}}
        </script>
        </body></html>
        """
        data = self.downloader._extract_json_blob(html)
        self.assertIn("__DEFAULT_SCOPE__", data)

    def test_extract_json_blob_fail(self) -> None:
        with self.assertRaises(TikTokDownloadError):
            self.downloader._extract_json_blob("<html></html>")

    def test_safe_filename(self) -> None:
        name = self.downloader._safe_filename('a/b:c*?"<>|\n')
        self.assertEqual(name, "a_b_c_")

    @patch("tiktok_downloader.requests.Session.get")
    def test_get_video_info(self, mock_get: Mock) -> None:
        redirect_resp = Mock()
        redirect_resp.raise_for_status = Mock()
        redirect_resp.url = "https://www.tiktok.com/@x/video/123"

        page_resp = Mock()
        page_resp.raise_for_status = Mock()
        page_resp.text = """
        <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">
        {"__DEFAULT_SCOPE__":{"webapp.video-detail":{"itemInfo":{"itemStruct":{"id":"123","desc":"demo","video":{"downloadAddr":"https://cdn/playwm/xx.mp4?watermark=1&is_play_url=1"}}}}}}
        </script>
        """

        mock_get.side_effect = [redirect_resp, page_resp]
        info = self.downloader.get_video_info("https://v.douyin.com/demo/")
        self.assertEqual(info.video_id, "123")
        self.assertEqual(info.description, "demo")
        self.assertIn("watermark=0", info.download_url)

    @patch("tiktok_downloader.requests.Session.get")
    def test_download_success(self, mock_get: Mock) -> None:
        download_resp = Mock()
        download_resp.__enter__ = Mock(return_value=download_resp)
        download_resp.__exit__ = Mock(return_value=False)
        download_resp.raise_for_status = Mock()
        download_resp.iter_content = Mock(return_value=[b"123", b"456"])
        mock_get.return_value = download_resp

        info = VideoInfo(video_id="123", description="hello", download_url="https://x/mp4")
        with TemporaryDirectory() as tmp:
            file_path = self.downloader.download(info, tmp)
            self.assertTrue(Path(file_path).exists())
            self.assertGreater(Path(file_path).stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
