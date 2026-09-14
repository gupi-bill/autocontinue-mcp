<div align="center">

# 🔁 autocontinue-mcp

**无限续写监工 — 一个 MCP Server，让任意 AI 网页被中断的长生成自动续写**

后台循环盯屏：截图 → OCR 认出「继续」按钮 → 自动点击，
像监工一样替你续上，长任务不断档，解放双手。

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![MCP](https://img.shields.io/badge/MCP-Server-green)](#接入-mcp-客户端)
[![LLM](https://img.shields.io/badge/LLM依赖-零-lightgrey)](#特性)
[![License](https://img.shields.io/badge/license-MIT-blue)](./LICENSE)

</div>

---

## 目录

- [💡 它解决什么问题](#-它解决什么问题)
- [✨ 特性](#-特性)
- [🔍 原理](#-原理)
- [📦 安装](#-安装)
- [🔌 接入 MCP 客户端](#-接入-mcp-客户端)
- [🛠️ 工具列表](#️-工具列表)
- [⚙️ 环境变量](#️-环境变量均可选)
- [🛡️ 安全须知](#️-安全须知)
- [🖥️ 平台支持](#️-平台支持)

---

## 💡 它解决什么问题

当你让某个网页 AI 跑一段很长的任务，它经常会因为「生成被中断 / 请点继续」而卡住。这个工具在后台循环盯屏：每几秒截一次图 → OCR 认出独立的「继续」按钮 → 自动点它，循环不断，像监工一样替你续上。

> 完全通用：通过环境变量配置按钮文字，可适配任意会弹出「继续 / 继续生成 / Resume / Continue」类按钮的网页或应用，**不绑定任何特定平台**。

---

## ✨ 特性

| 特性 | 说明 |
|------|------|
| 🔁 **无限续写** | AI 网页一中断就自动点「继续」，循环盯死，长任务不断档 |
| 🌐 **完全通用** | 默认适配中文「继续」类按钮，改 `AC_KEYWORDS` 即可适配英文（Resume / Continue）或任意文字 |
| 🎯 **精准识别** | 只认独立的短按钮，自动过滤正文里的「继续读取…」等长句误命中 |
| 🖥️ **跨平台** | Windows / macOS / Linux 均可（权限配置见下） |
| 🛡️ **安全可控** | 仅在主动 `start` 后动作；鼠标甩屏幕左上角即可紧急停止；不碰你的文件 |
| ⚙️ **零大模型依赖** | 纯 pyautogui + OCR，不涉及任何 LLM / 向量 / 云端 |

---

## 🔍 原理

```
循环（每 interval 秒）:
  1. 全屏（或指定区域）截图，存系统临时目录
  2. OCR 识别屏幕文字
  3. 只认「独立的短按钮」（如「继续」「继续生成」），
     过滤正文里的长句（如"继续读取关键文件"）
  4. 命中 → 点击按钮中心；未命中 → 静默等待下一轮
  直到你调用 stop，或把鼠标甩到屏幕左上角紧急停止
```

`pyautogui` 和 OCR 引擎均为**延迟导入**，在无桌面环境（如纯服务器）上也能正常加载 Server，只是无法真正点击。

---

## 📦 安装

需要 Python 3.10+。

```bash
git clone https://github.com/<你的用户名>/autocontinue-mcp.git
cd autocontinue-mcp
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> 📌 首次运行会自动下载 OCR 模型（约几十 MB），请保持联网。

---

## 🔌 接入 MCP 客户端

把下面这段加进你的 MCP 配置文件（WorkBuddy / Claude Desktop / 任意支持 stdio MCP 的客户端）。注意把 `args` 里的路径换成你本机的**绝对路径**：

```json
{
  "mcpServers": {
    "autocontinue": {
      "command": "python",
      "args": ["/absolute/path/to/autocontinue-mcp/server.py"],
      "env": {
        "AC_KEYWORDS": "继续,继续生成,继续回复",
        "AC_INTERVAL": "5"
      },
      "disabled": false
    }
  }
}
```

更完整的示例见 [`mcp-config.example.json`](./mcp-config.example.json)。

---

## 🛠️ 工具列表

| 工具 | 作用 |
| --- | --- |
| `autocontinue_start(interval=5.0)` | 启动无限续写监工，循环扫描并自动点「继续」 |
| `autocontinue_stop()` | 停止监工 |
| `autocontinue_status()` | 查看状态：是否在跑、扫描次数、最近动作、最近检测到的按钮 |
| `autocontinue_scan_once()` | 单次扫描并点击（不进入循环），用于手动试探 |

---

## ⚙️ 环境变量（均可选）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `AC_KEYWORDS` | `继续,继续生成,继续回复` | 要识别的按钮文字，逗号分隔 |
| `AC_INTERVAL` | `5` | 扫描间隔秒（也可用 `start` 的 `interval` 参数覆盖） |
| `AC_REGION` | 全屏 | 扫描区域 `"x,y,w,h"`（相对屏幕左上角），缩小范围可提速 |
| `AC_MIN_LEN` | `2` | 按钮文字最小长度过滤 |
| `AC_MAX_LEN` | `4` | 按钮文字最大长度过滤（过滤正文长句误命中） |

**示例** —— 适配英文网页（"Resume" / "Continue" 按钮）：

```json
"env": { "AC_KEYWORDS": "Resume,Continue,继续", "AC_INTERVAL": "4" }
```

---

## 🛡️ 安全须知

- **真实鼠标键盘操作 = 高权限**。本工具会真的移动并点击你的鼠标，请只在可信环境使用，且仅在你主动 `start` 后才会动作；
- **紧急停止**：把鼠标**快速甩到屏幕左上角**即可触发 `pyautogui.FAILSAFE`，监工会立刻中止；
- **不会读取 / 修改你的文件**，只会截图（存系统临时目录，用完即删）并点击；
- 建议先用 `autocontinue_scan_once()` 手动确认能正确识别目标按钮，再启动长期监工。

---

## 🖥️ 平台支持

| 平台 | 状态 |
| --- | --- |
| Windows | ✅ 推荐，测试最充分 |
| macOS | ⚠️ 需授予「辅助功能 / 屏幕录制」权限 |
| Linux | ⚠️ 需 X11 环境 + `scrot` / `xwd` 等截图后端 |

---

## License

[MIT](./LICENSE)
