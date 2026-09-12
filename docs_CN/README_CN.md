<p align="right">
  <a href="../README.md">English</a> | <strong>中文</strong>
</p>

<h1 align="center">💻 Lamarck Translator</h1>

<p align="center"><em>—— 2026.09.12</em></p>

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/GUI-PySide6-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/Backend-Codex%20CLI-9cf?style=flat-square" />
  <img src="https://img.shields.io/badge/Platform-Windows-555?style=flat-square" />
  <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square" />
</p>

---

## 项目背景

一个常驻托盘的 **Windows 划词与截图翻译工具**，为读英文文献而做。在浏览器或 Zotero 里选中一句话按 `Alt+C`，或者在扫描版 PDF、图表上框一个框按 `Alt+S`，结果都以逐句英中对照的形式返回。

它和常见翻译工具的区别在后端：它调用**本机的 `codex` CLI**，直接复用那里已经保存的登录状态。项目本身不配置、不保存、也不读取任何翻译 API Key —— 翻译跑在这台机器上当前登录的那个 Codex 账号上。

默认提示词是按科研阅读调过的：保留专业术语、缩写、公式、残基编号、链名、文件路径、命令和参数，必要时在中文术语后用括号保留英文。

## 工作流程

```
Alt+C   划词      ->  模拟 Ctrl+C        ->  codex exec          ->  句对  ->  双语卡片
Alt+S   框选截图  ->  按 DPI 换算裁 PNG  ->  codex exec --image  ->  句对  ->  双语卡片
```

三处是主要难点：

- **把选区从源程序里取出来。** 按下热键并不能直接读到选区，程序是替你按一次 `Ctrl+C` —— 这件事在 Windows 上远没有听起来可靠。取词器会先清空剪贴板，这样"剪贴板里有东西"本身就等于复制成功，残留内容不会被当成新选区；再等物理按键松开，否则你手还压着 Alt，发出去的 `Ctrl+C` 到达目标程序时是 `Ctrl+Alt+C`；然后把焦点抢回原窗口，并按四种复制手段逐级降级 —— `SendInput` 发 `Ctrl+C`、给焦点控件发 `WM_COPY`、老式 `keybd_event`、`Ctrl+Insert` —— 全部失败才放弃。完事后把原剪贴板内容还原。

- **要求结构化输出。** 提示词不是简单的"翻译一下"，而是要求模型按自然句切分、把每句英文原样回传，并返回 `{"pairs": [{"source": ..., "translation": ...}]}`。回传原文是英中卡片能够配对的前提；在截图模式下它还兼了一职：程序自己不做 OCR，英文那一侧完全来自模型从图里读出来的内容。

- **以最小权限调用 Codex。** 每次翻译是一条 `codex exec`，工作目录是个临时空文件夹，只读沙盒，临时会话，并且不加载本机的 `config.toml` 和 `.rules`。翻译任务不需要访问这台机器，就一点权限都不给。

## 内容索引

| 文件                                                                     | 说明                                                    |
| :----------------------------------------------------------------------- | :------------------------------------------------------- |
| [main.py](../src/lamarck_translator/main.py)                             | 托盘程序、热键接线、翻译任务调度                        |
| [clipboard.py](../src/lamarck_translator/clipboard.py)                   | 划词取词：四级复制降级、剪贴板保存与恢复                |
| [screenshot.py](../src/lamarck_translator/screenshot.py)                 | 全屏遮罩、拖拽框选、按 DPI 换算的裁剪                   |
| [backend.py](../src/lamarck_translator/backend.py)                       | 定位 `codex.exe`，构造沙盒化的 `codex exec` 调用        |
| [prompts.py](../src/lamarck_translator/prompts.py)                       | 文字 / 图片两种输入的提示词构造                         |
| [translation_pairs.py](../src/lamarck_translator/translation_pairs.py)   | 把结构化响应解析成句对                                  |
| [result_window.py](../src/lamarck_translator/result_window.py)           | 无边框结果窗口、双语句对卡片、悬停联动高亮              |
| [identity.py](../src/lamarck_translator/identity.py)                     | 从本机 `auth.json` 的 ID Token 读当前登录的 Codex 账号  |
| [hotkeys.py](../src/lamarck_translator/hotkeys.py)                       | 用 `RegisterHotKey` + `WM_HOTKEY` 注册全局热键          |
| [config.py](../src/lamarck_translator/config.py)                         | 配置文件的读取与写入                                    |
| [worker.py](../src/lamarck_translator/worker.py)                         | 后台翻译任务、临时截图清理                              |
| [tests/](../tests/)                                                      | 25 个 pytest 测试                                       |
| [build.ps1](../build.ps1)                                                | PyInstaller 打包脚本                                    |

---

## 安装与运行

要求 **Windows 10/11**、**Python 3.10+**、本机已安装 **Codex CLI**。

```powershell
cd F:\VScode\LamarckCC\040_Lamarck_Translator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
codex login
python -m lamarck_translator
```

也可以直接运行：

```powershell
.\run.ps1
```

第一次使用前执行一次 `codex login`。Codex CLI 可以用 ChatGPT 登录，也可以用 API Key 登录；本程序只调用 CLI，不读取也不写入它的认证文件。

## 使用方法

**划词翻译**

1. 在浏览器、Zotero 或大多数能复制文字的软件里选中英文。
2. 按 `Alt+C`。
3. 程序替你按一次 `Ctrl+C`，恢复你原来的剪贴板，然后显示完整的逐句对照翻译。
4. 把鼠标移到任意英文或中文句子上，对应的另一半会同步高亮。

**截图翻译**

1. 把鼠标放在目标屏幕上，按 `Alt+S`。
2. 按住鼠标左键框选内容。
3. 松开即提交，按 `Esc` 取消。

托盘菜单可以触发同样的两个操作，也可以检查 Codex 登录状态或退出程序。窗口标题区显示本机 Codex CLI 当前登录的 OpenAI 账号；切换账号后会在下一次翻译时刷新。它上面那一行标明每次翻译使用的模型和 reasoning effort，与实际传给 Codex 的值完全一致；要修改请改配置文件。

> **提示：** 某些软件复制大段文字较慢。如果 `Alt+C` 在长段落上取不到内容，调大 `clipboard_wait_ms`。

## 配置

首次启动后生成在：

```text
%APPDATA%\LamarckTranslator\config.json
```

| 键名                | 默认值            | 说明                                                        |
| :------------------ | :---------------- | :----------------------------------------------------------- |
| `text_hotkey`       | `Alt+C`           | 划词翻译快捷键                                              |
| `screenshot_hotkey` | `Alt+S`           | 截图翻译快捷键                                              |
| `model`             | `gpt-5.6-sol`     | 传给 `codex exec --model`；留空则用当前 Codex 默认模型      |
| `reasoning_effort`  | `high`            | 设置 `model_reasoning_effort`；留空则不传                   |
| `timeout_seconds`   | `120`             | 超过这个秒数 Codex 还没返回就放弃                           |
| `clipboard_wait_ms` | `220`             | 等待源程序把内容写进剪贴板的时长                            |
| `restore_clipboard` | `true`            | 取词结束后把原剪贴板内容还原                                |
| `prompt`            | 科研翻译风格      | 只管翻译风格；结构化输出格式由程序自动追加                  |

快捷键写作 `修饰键+主键`，修饰键为 `Ctrl` / `Alt` / `Shift` / `Win`，主键为单个字母或数字，或 `F1`–`F24`。改完配置需要重启程序。

## 打包

```powershell
python -m pip install -e ".[dev]"
.\build.ps1
```

产物是单目录形式的 `dist\LamarckTranslator\LamarckTranslator.exe`。打包后的程序仍然要求本机装有 `codex.exe` 并已登录 —— 它打包的是前端，不是后端。

## 隐私与安全

- 选中的文字和截图会发送给本机当前登录的 Codex 服务处理。
- 不记录任何东西：不留原文、不留译文、不留截图历史。截图写入系统临时目录，请求一返回就立即删除。
- 账号显示只读取本机 Codex `auth.json` 中 ID Token 的 `email` 和 `name` 声明。access token、refresh token 和 API Key 一律不显示、不保存、不上传。
- 每次翻译都在临时空目录下以只读沙盒、临时会话运行。
- 不要把 Codex 登录缓存、API Key 或含有密钥的配置文件提交到 Git。

## 当前限制

- 划词模式靠复制取词，少数禁用复制的软件读不到，这类场景请改用截图模式。
- 剪贴板恢复是靠克隆 Qt 能看到的 MIME 数据；某些软件的私有剪贴板格式可能无法完整还原。
- 截图模式一次框选一个屏幕，跨两块显示器的矩形尚不支持。
- 快捷键若已被其他程序占用，启动时注册失败并给出提示。

---

##### 翻译由 [Codex CLI](https://github.com/openai/codex) 驱动，需在本机安装并完成登录。
