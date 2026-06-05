from __future__ import annotations

import unittest

from app.common.exceptions import AppException
from app.utils.url_util import (
    detect_source_type,
    detect_url_type,
    extract_first_url,
    extract_video_links,
    normalize_url,
    parse_material_input,
)


class UrlUtilTest(unittest.TestCase):
    def test_case_1_extract_douyin_share_text(self):
        text = "7.43 pda:/ 让你在几秒钟之内记住我  https://v.douyin.com/L5pbfdP/ 复制此链接，打开Dou音搜索，直接观看视频！"
        links = extract_video_links(text)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["normalizedUrl"], "https://v.douyin.com/L5pbfdP/")
        self.assertEqual(links[0]["sourceType"], "douyin")
        self.assertEqual(links[0]["urlType"], "douyin_short")

    def test_case_2_extract_douyin_short_url(self):
        url = "https://v.douyin.com/L4FJNR3/"
        self.assertEqual(extract_first_url(url), "https://v.douyin.com/L4FJNR3/")
        self.assertEqual(normalize_url(url), "https://v.douyin.com/L4FJNR3/")
        self.assertEqual(detect_source_type(url), "douyin")
        self.assertEqual(detect_url_type(url), "douyin_short")

    def test_case_3_extract_douyin_video_url(self):
        url = "https://www.douyin.com/video/6914948781100338440"
        self.assertEqual(normalize_url(url), url)
        self.assertEqual(detect_source_type(url), "douyin")
        self.assertEqual(detect_url_type(url), "douyin_video")

    def test_case_4_normalize_douyin_discover_url(self):
        url = "https://www.douyin.com/discover?modal_id=7069543727328398622"
        self.assertEqual(normalize_url(url), "https://www.douyin.com/video/7069543727328398622")
        self.assertEqual(detect_source_type(url), "douyin")
        self.assertEqual(detect_url_type(url), "douyin_discover")

    def test_case_5_extract_tiktok_short_url(self):
        url = "https://www.tiktok.com/t/ZTR9nDNWq/"
        self.assertEqual(normalize_url(url), url)
        self.assertEqual(detect_source_type(url), "tiktok")
        self.assertEqual(detect_url_type(url), "tiktok_short")

    def test_case_6_extract_tiktok_video_url(self):
        url = "https://www.tiktok.com/@evil0ctal/video/7156033831819037994"
        self.assertEqual(normalize_url(url), url)
        self.assertEqual(detect_source_type(url), "tiktok")
        self.assertEqual(detect_url_type(url), "tiktok_video")

    def test_case_7_extract_multiple_links_in_order(self):
        text = "\n".join(
            [
                "https://v.douyin.com/L4NpDJ6/",
                "https://www.douyin.com/video/7126745726494821640",
                "2.84 nqe:/ 骑白马的也可以是公主%%百万转场变身https://v.douyin.com/L4FJNR3/ 复制此链接，打开Dou音搜索，直接观看视频！",
                "https://www.tiktok.com/t/ZTR9nkkmL/",
                "https://www.tiktok.com/t/ZTR9nDNWq/",
                "https://www.tiktok.com/@evil0ctal/video/7156033831819037994",
            ]
        )
        links = extract_video_links(text)
        self.assertEqual(
            [item["normalizedUrl"] for item in links],
            [
                "https://v.douyin.com/L4NpDJ6/",
                "https://www.douyin.com/video/7126745726494821640",
                "https://v.douyin.com/L4FJNR3/",
                "https://www.tiktok.com/t/ZTR9nkkmL/",
                "https://www.tiktok.com/t/ZTR9nDNWq/",
                "https://www.tiktok.com/@evil0ctal/video/7156033831819037994",
            ],
        )

    def test_case_8_no_url(self):
        self.assertEqual(extract_video_links("这个没有链接"), [])
        with self.assertRaises(AppException) as context:
            parse_material_input("这个没有链接", "auto")
        self.assertEqual(context.exception.data["errorType"], "url_not_found")

    def test_parse_material_input_prefers_explicit_url(self):
        parsed = parse_material_input(
            "0.02 复制打开抖音，看看【沈柳名的作品】ChatGPT Plus 免费了？ https://v.douyin.com/w2_bZi78r3k/ SYZ:/ :0pm 08/20 S@Y.ZZ",
            "auto",
            "https://www.douyin.com/discover?modal_id=7069543727328398622",
        )
        self.assertEqual(parsed.normalized_url, "https://www.douyin.com/video/7069543727328398622")
        self.assertEqual(parsed.source_type, "douyin")
        self.assertEqual(parsed.url_type, "douyin_discover")
        self.assertEqual(parsed.urls, ["https://www.douyin.com/video/7069543727328398622"])


if __name__ == "__main__":
    unittest.main()
