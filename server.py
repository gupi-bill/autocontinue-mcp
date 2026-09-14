"""
autocontinue-mcp — 无限续写监工 MCP Server
无限续写监工：自动点击任意 AI 网页上中断后弹出的「继续」按钮，
让被中断的长生成自动续写，循环盯死，像监工一样。

Stack: FastMCP + pyautogui + rapidocr-onnxruntime
pyautogui / rapidocr 延迟导入，无桌面环境也能加载（只是无法真正点击）。

环境变量配置（均可选，均有合理默认值）：
  AC_KEYWORDS   要识别的按钮文字，逗号分隔。默认 "继续,继续生成,继续回复"
  AC_INTERVAL   扫描间隔秒。默认 5
  AC_REGION     扫描区域 "x,y,w,h"（相对屏幕左上角）。默认全屏（None）
  AC_MIN_LEN    按钮文字最小长度过滤。默认 2
  AC_MAX_LEN    按钮文字最大长度过滤。默认 4（过滤正文里的"继续读取…"长句）

安全：pyautogui FAILSAFE 开启 —— 把鼠标急甩到屏幕左上角即可紧急停止。
"""
import os
import tempfile
import threading
import time

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("autocontinue")

STATE = {
    "running": False,
    "thread": None,
    "ocr": None,
    "tick": 0,
    "last_action": "未启动",
    "last_detect": None,
}
LOCK = threading.Lock()


def _keywords():
    """从环境变量读取要识别的按钮文字列表。"""
    raw = os.environ.get("AC_KEYWORDS", "继续,继续生成,继续回复")
    return [k.strip() for k in raw.split(",") if k.strip()]


def _is_btn(text):
    """只认独立的「继续」类按钮，忽略正文里的长句（如"继续读取关键文件"）。"""
    t = (text or "").strip()
    if not t:
        return False
    kws = _keywords()
    if t in kws:
        return True
    min_len = int(os.environ.get("AC_MIN_LEN", "2"))
    max_len = int(os.environ.get("AC_MAX_LEN", "4"))
    return any(k in t for k in kws) and min_len <= len(t) <= max_len


def _region():
    """从环境变量读取扫描区域，格式 "x,y,w,h"，无效返回 None（全屏）。"""
    r = os.environ.get("AC_REGION")
    if not r:
        return None
    try:
        x, y, w, h = (int(v) for v in r.split(","))
        return (x, y, w, h)
    except ValueError:
        return None


def _get_ocr():
    """懒加载并缓存 OCR 引擎（首次较慢，会在 start 时预热）。"""
    if STATE["ocr"] is None:
        from rapidocr_onnxruntime import RapidOCR
        STATE["ocr"] = RapidOCR()
    return STATE["ocr"]


def _scan_once():
    """截图 + OCR，命中按钮返回 (cx, cy, text, score)，否则 None。截图存系统临时目录，用完即删。"""
    import pyautogui

    region = _region()
    fd, path = tempfile.mkstemp(suffix=".png", prefix="ac_shot_")
    os.close(fd)
    try:
        if region:
            pyautogui.screenshot(region=region).save(path)
        else:
            pyautogui.screenshot().save(path)
        res, _ = _get_ocr()(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if not res:
        return None
    for box, text, score in res:
        if _is_btn(text):
            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
            cx = int(sum(xs) / len(xs))
            cy = int(sum(ys) / len(ys))
            return (cx, cy, str(text), float(score))
    return None


def _loop(interval):
    """后台循环：截图→OCR→命中则点击，直到被 stop 或 FAILSAFE 打断。"""
    import pyautogui

    pyautogui.FAILSAFE = True  # 鼠标甩左上角可紧急停止
    while True:
        with LOCK:
            if not STATE["running"]:
                break
        try:
            hit = _scan_once()
        except pyautogui.FailSafeException:
            with LOCK:
                STATE["running"] = False
                STATE["last_action"] = "触发 FAILSAFE，已紧急停止"
            break
        with LOCK:
            STATE["tick"] += 1
            if hit:
                cx, cy, txt, sc = hit
                try:
                    pyautogui.click(cx, cy)
                    STATE["last_action"] = (
                        f"第{STATE['tick']}次扫描命中「{txt}」"
                        f"score={sc:.2f}→已点击({cx},{cy})"
                    )
                    STATE["last_detect"] = (cx, cy, txt)
                except pyautogui.FailSafeException:
                    STATE["running"] = False
                    STATE["last_action"] = "触发 FAILSAFE，已紧急停止"
                    break
            else:
                STATE["last_action"] = f"第{STATE['tick']}次扫描：未检测到继续按钮"
                STATE["last_detect"] = None
        time.sleep(interval)


@mcp.tool()
def autocontinue_start(interval: float = 5.0) -> str:
    """启动「无限续写」监工：循环扫描屏幕，AI 网页一出现独立的「继续」按钮就自动点击，
    直到调用 autocontinue_stop 或把鼠标甩到屏幕左上角紧急停止。
    interval: 扫描间隔秒（默认 5，也可用环境变量 AC_INTERVAL 覆盖）。"""
    with LOCK:
        if STATE["running"]:
            return "无限续写监工已在运行中"
        iv = interval if interval and interval > 0 else float(
            os.environ.get("AC_INTERVAL", "5")
        )
        STATE["running"] = True
        STATE["thread"] = threading.Thread(
            target=_loop, args=(iv,), daemon=True
        )
        STATE["thread"].start()
    try:
        _get_ocr()  # 预热 OCR 模型（首次较慢）
    except Exception as e:
        return f"已启动但 OCR 预热失败：{e}"
    return f"无限续写监工已启动，每 {iv} 秒扫描一次。AI 网页一停就自动点继续。"


@mcp.tool()
def autocontinue_stop() -> str:
    """停止无限续写监工。"""
    with LOCK:
        if not STATE["running"]:
            return "监工本来就没在运行"
        STATE["running"] = False
    return "已停止无限续写监工。"


@mcp.tool()
def autocontinue_status() -> dict:
    """返回监工状态：是否在跑、扫描次数、最近动作、最近检测到的按钮。"""
    with LOCK:
        return {
            "running": STATE["running"],
            "tick": STATE["tick"],
            "last_action": STATE["last_action"],
            "last_detect": STATE["last_detect"],
        }


@mcp.tool()
def autocontinue_scan_once() -> dict:
    """单次扫描：检测屏幕是否有「继续」按钮，有则点击并返回命中信息，无则返回未触发。"""
    hit = _scan_once()
    if hit:
        import pyautogui

        cx, cy, txt, sc = hit
        pyautogui.click(cx, cy)
        return {"clicked": True, "text": txt, "score": sc, "at": (cx, cy)}
    return {"clicked": False, "text": None}


if __name__ == "__main__":
    mcp.run()
