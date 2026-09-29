"""autocontinue-mcp 单元测试。

跑法（不需要装任何第三方库）：
    python3 -m unittest test_server -v
    python3 test_server.py
"""
import importlib
import os
import unittest
from unittest.mock import MagicMock, patch

import server

# 这些键在测试里会被反复改，每次用完还原，免得污染真实环境
_ENV_KEYS = ("AC_KEYWORDS", "AC_REGION")


class KeywordsParsingTest(unittest.TestCase):
    """环境变量解析关键词列表。"""

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in _ENV_KEYS}
        importlib.reload(server)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(server)

    def test_comma_separated(self):
        os.environ["AC_KEYWORDS"] = "continue,resume,keep"
        self.assertEqual(server._keywords(), ["continue", "resume", "keep"])

    def test_preserves_case_and_order(self):
        """关键词区分大小写、保持原顺序（OCR 输出是原样大小写）。"""
        os.environ["AC_KEYWORDS"] = "Resume,Continue"
        self.assertEqual(server._keywords(), ["Resume", "Continue"])

    def test_default_when_unset(self):
        os.environ.pop("AC_KEYWORDS", None)
        importlib.reload(server)
        self.assertTrue(server._keywords())  # 至少要有默认词，否则等于没开


class IsBtnTest(unittest.TestCase):
    """按钮识别：精确匹配通过，长句过滤掉。"""

    def setUp(self):
        os.environ["AC_KEYWORDS"] = "continue,resume"
        importlib.reload(server)

    def tearDown(self):
        os.environ["AC_KEYWORDS"] = "continue,resume"
        importlib.reload(server)

    def test_exact_match(self):
        self.assertIs(server._is_btn("continue"), True)
        self.assertIs(server._is_btn("resume"), True)

    def test_rejects_long_sentence(self):
        """整句不是按钮名 —— 否则会点错地方。"""
        self.assertIs(server._is_btn("continue reading the document"), False)

    def test_rejects_empty_and_none(self):
        self.assertIs(server._is_btn(""), False)
        self.assertIs(server._is_btn(None), False)


class RegionParsingTest(unittest.TestCase):
    """扫描区域解析。"""

    def tearDown(self):
        os.environ.pop("AC_REGION", None)
        importlib.reload(server)

    def test_unset_means_whole_screen(self):
        os.environ.pop("AC_REGION", None)
        importlib.reload(server)
        self.assertIsNone(server._region())

    def test_four_ints(self):
        os.environ["AC_REGION"] = "100,200,500,400"
        importlib.reload(server)
        self.assertEqual(server._region(), (100, 200, 500, 400))

    def test_invalid_falls_back_to_none(self):
        os.environ["AC_REGION"] = "invalid"
        importlib.reload(server)
        self.assertIsNone(server._region())


class ScanOnceTest(unittest.TestCase):
    """_scan_once 在 OCR 不可用时应返回 None 而不是抛异常。"""

    def setUp(self):
        os.environ["AC_KEYWORDS"] = "continue"
        importlib.reload(server)
        server.STATE["ocr"] = None

    def test_returns_none_when_ocr_finds_nothing(self):
        """有桌面环境但 OCR 没命中 → None。"""
        with patch.dict("sys.modules", {"pyautogui": MagicMock()}):
            mock_ocr = MagicMock(return_value=(None, None))
            with patch("server._get_ocr", return_value=mock_ocr):
                self.assertIsNone(server._scan_once())
            mock_ocr.assert_called_once()

    def test_no_exception_when_ocr_missing(self):
        """连 rapidocr 都没装时，也不能把调用方带崩。"""
        with patch.dict("sys.modules", {"pyautogui": MagicMock()}):
            with patch("server._get_ocr", side_effect=RuntimeError("no ocr")):
                self.assertIsNone(server._scan_once())

    def test_returns_none_without_desktop(self):
        """无桌面环境（服务器/容器/CI）没有 pyautogui → None，不抛异常。

        这是真实场景：CI 里跑测试根本没有 X server。
        """
        with patch.dict("sys.modules", {"pyautogui": None}):
            self.assertIsNone(server._scan_once())


class StartStopTest(unittest.TestCase):
    """监工启动和停止。"""

    def setUp(self):
        importlib.reload(server)
        server.STATE["running"] = False

    def tearDown(self):
        server.STATE["running"] = False

    def test_start_then_stop(self):
        with patch("server._get_ocr"), patch("server._loop") as mock_loop:
            result = server.autocontinue_start(interval=1.0)
            self.assertIn("已启动", result)
            mock_loop.assert_called_once()

        server.STATE["running"] = True
        result = server.autocontinue_stop()
        self.assertIn("已停止", result)
        self.assertIs(server.STATE["running"], False)

    def test_stop_when_not_running(self):
        result = server.autocontinue_stop()
        self.assertIn("没在运行", result)


class StatusTest(unittest.TestCase):
    """status 工具返回正确格式。"""

    def setUp(self):
        importlib.reload(server)

    def test_reports_state(self):
        server.STATE["running"] = True
        server.STATE["tick"] = 5
        server.STATE["last_action"] = "test"
        server.STATE["last_detect"] = (100, 200, "cont")

        status = server.autocontinue_status()
        self.assertIsInstance(status, dict)
        self.assertIs(status["running"], True)
        self.assertEqual(status["tick"], 5)
        self.assertEqual(status["last_action"], "test")
        self.assertEqual(status["last_detect"], (100, 200, "cont"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
