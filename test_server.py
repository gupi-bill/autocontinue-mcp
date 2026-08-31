"""autocontinue-mcp 基础单元测试。"""
import os
from unittest.mock import patch, MagicMock


def test_keywords_parsing():
    """环境变量解析关键词列表。"""
    os.environ["AC_KEYWORDS"] = "continue,resume,keep"
    from server import _keywords
    assert _keywords() == ["continue", "resume", "keep"]

    os.environ["AC_KEYWORDS"] = "Resume,Continue"
    assert _keywords() == ["Resume", "Continue"]


def test_is_btn_basic():
    """按钮识别：精确匹配通过，长句过滤掉。"""
    os.environ["AC_KEYWORDS"] = "continue,resume"
    # Re-import to pick up new env
    import importlib
    import server
    importlib.reload(server)

    assert server._is_btn("continue") is True
    assert server._is_btn("resume") is True
    assert server._is_btn("continue reading the document") is False
    assert server._is_btn("") is False
    assert server._is_btn(None) is False


def test_region_parsing():
    """扫描区域解析。"""
    os.environ.pop("AC_REGION", None)
    import importlib
    import server
    importlib.reload(server)

    assert server._region() is None

    os.environ["AC_REGION"] = "100,200,500,400"
    importlib.reload(server)
    assert server._region() == (100, 200, 500, 400)

    os.environ["AC_REGION"] = "invalid"
    importlib.reload(server)
    assert server._region() is None


def test_scan_once_no_ocr():
    """无 OCR 时 _scan_once 返回 None 而不是抛异常。"""
    import server
    server.STATE["ocr"] = None
    os.environ["AC_KEYWORDS"] = "continue"

    mock_ocr = MagicMock(return_value=(None, None))
    with patch("server._get_ocr", return_value=mock_ocr):
        result = server._scan_once()
        assert result is None
        mock_ocr.assert_called_once()


def test_loop_start_stop():
    """监工启动和停止。"""
    import server
    assert server.STATE["running"] is False

    with patch("server._get_ocr"):
        with patch("server._loop") as mock_loop:
            result = server.autocontinue_start(interval=1.0)
            assert "已启动" in result
            mock_loop.assert_called_once()

    server.STATE["running"] = True
    result = server.autocontinue_stop()
    assert "已停止" in result
    assert server.STATE["running"] is False

    result = server.autocontinue_stop()
    assert "没在运行" in result


def test_status_returns_dict():
    """status 工具返回正确格式。"""
    import server
    server.STATE["running"] = True
    server.STATE["tick"] = 5
    server.STATE["last_action"] = "test"
    server.STATE["last_detect"] = (100, 200, "cont")

    status = server.autocontinue_status()
    assert isinstance(status, dict)
    assert status["running"] is True
    assert status["tick"] == 5
    assert status["last_action"] == "test"
    assert status["last_detect"] == (100, 200, "cont")
