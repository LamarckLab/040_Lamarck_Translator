# Lamarck Translator

一个面向 Windows 的个人划词与截图翻译工具。它调用本机 `codex` CLI，默认复用 Codex 已保存的登录状态，不在项目中保存 API Key。

## 当前功能

- `Alt+C`：复制当前选中的文字并翻译，适用于浏览器、Zotero 和大多数能复制文字的软件。
- `Alt+S`：在鼠标所在屏幕框选截图并翻译，适用于扫描 PDF、图片和图表。
- 系统托盘菜单可触发相同操作、检查 Codex 状态或退出。
- 划词结果按“英文原句—中文译文”逐句交替显示；鼠标悬停时对应英中句对同步高亮。
- 结果浮窗支持复制完整双语文本、重新翻译和关闭。
- 窗口标题区显示本机 Codex CLI 当前登录的 OpenAI 账号邮箱；切换账号后会在下一次翻译时刷新。
- 翻译提示词、快捷键、模型、超时和剪贴板恢复行为均可配置。

## 安装与运行

要求：Windows 10/11、Python 3.10+、本机 Codex CLI。

```powershell
cd F:\VScode\LamarckCC\040_Lamarck_Translator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
codex login
python -m lamarck_translator
```

也可以运行：

```powershell
.\run.ps1
```

第一次使用前执行 `codex login`。Codex CLI 可以使用 ChatGPT 登录，也可以使用 API Key 登录。程序只调用 CLI，不读取或保存认证文件。

## 使用方法

### 划词翻译

1. 在浏览器或 Zotero 中选中英文。
2. 按 `Alt+C`。
3. 程序模拟一次 `Ctrl+C`，取得文字后恢复原剪贴板，并显示完整的逐句英中对照翻译。
4. 将鼠标移到任意英文或中文句子上，对应的英中句对会同步高亮。

提示：某些软件复制大量文本较慢，可在配置中增大 `clipboard_wait_ms`。

### 截图翻译

1. 将鼠标放在目标屏幕上，按 `Alt+S`。
2. 按住鼠标左键框选内容。
3. 松开后自动提交；按 `Esc` 取消。

截图写入系统临时目录，请求结束后立即删除，不保留历史副本。

## 配置

首次启动后生成：

```text
%APPDATA%\LamarckTranslator\config.json
```

默认配置示例：

```json
{
  "text_hotkey": "Alt+C",
  "screenshot_hotkey": "Alt+S",
  "model": "gpt-5.6-sol",
  "reasoning_effort": "high",
  "timeout_seconds": 120,
  "clipboard_wait_ms": 220,
  "restore_clipboard": true,
  "prompt": "..."
}
```

`model` 留空时使用当前 Codex 默认模型。修改配置后需要重启程序。

## 打包 EXE

```powershell
python -m pip install -e ".[dev]"
.\build.ps1
```

输出位于 `dist\LamarckTranslator.exe`。打包后的程序仍要求本机能找到 `codex.exe` 并已登录。

## 当前限制

- 第一版通过复制取得选区；少数禁用复制的软件无法使用划词模式，可改用截图模式。
- 为尽量恢复剪贴板，程序复制 Qt 可读取的 MIME 数据；某些软件的私有剪贴板格式仍可能无法完整还原。
- 截图模式一次框选一个屏幕。跨两个屏幕的矩形选择尚未实现。
- 快捷键若被其他程序占用，启动时会提示注册失败。

## 隐私与安全

- 选中文字或截图会发送给当前登录的 Codex 服务进行处理。
- 项目不记录原文、译文或截图历史。
- 账号显示只从本机 Codex `auth.json` 的 ID Token 公开声明中读取邮箱或姓名；不会显示、保存或上传 access token、refresh token 或 API Key。
- 不要把 Codex 登录缓存、API Key 或包含密钥的配置提交到 Git。
- 后端使用临时空目录、只读沙盒和临时会话运行翻译。
