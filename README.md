<p align="right">
  <strong>English</strong> | <a href="./docs_CN/README_CN.md">中文</a>
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

## Overview

A tray-resident **selection and screenshot translator for Windows**, for reading English material of any kind — a paper, a library's documentation, an issue thread, an error dialog. Select a sentence in a browser or in Zotero and press `Alt+C`; drag a box over a scanned PDF, a figure, or anything that will not let you select text, and press `Alt+S`. Either way the result comes back as sentence-by-sentence English–Chinese pairs.

What sets it apart from the usual translation utility is the backend: it shells out to the **local `codex` CLI** and reuses the login already stored there. No translation API key is configured, stored, or read by this project — translation runs on whichever Codex account is signed in on the machine.

The default prompt is tuned for technical reading, across protein science, structural biology, machine learning, and software engineering. It preserves terminology, abbreviations, formulas, residue numbers, chain names, file paths, commands, and flags, and keeps the English in parentheses after a Chinese term where that helps.

## How It Works

```
Alt+C   selection    ->  simulated Ctrl+C      ->  codex exec          ->  sentence pairs  ->  bilingual cards
Alt+S   screen box   ->  DPI-correct PNG crop  ->  codex exec --image  ->  sentence pairs  ->  bilingual cards
```

Three parts carry most of the weight:

- **Getting the selection out of the source app.** The hotkey does not read the selection directly. It presses `Ctrl+C` for you, which on Windows is less reliable than it sounds. The reader clears the clipboard first, so a stale value can never be mistaken for a fresh copy; waits for the physical hotkey keys to be released, since otherwise `Ctrl+C` arrives as `Ctrl+Alt+C`; restores focus to the original window; and escalates through four copy methods before giving up — `SendInput` `Ctrl+C`, `WM_COPY` to the focused control, `keybd_event`, and `Ctrl+Insert`. The original clipboard contents are put back afterwards.

- **Asking for structured output.** The model is not asked simply to translate. It is asked to split the text into natural sentences, echo each English sentence back verbatim, and return `{"pairs": [{"source": ..., "translation": ...}]}`. Echoing the source is what makes the linked bilingual cards possible, and in screenshot mode it does double duty: the app runs no OCR of its own, so the English side comes entirely from what the model reads off the image.

- **Running Codex with the smallest possible footprint.** Each translation is one `codex exec` call in a temporary empty directory, under a read-only sandbox, in an ephemeral session, with the local `config.toml` and `.rules` files ignored. A translation needs no access to the machine, so it is given none.

## Contents

| File                                                                  | Description                                                            |
| :-------------------------------------------------------------------- | :---------------------------------------------------------------------- |
| [main.py](./src/lamarck_translator/main.py)                           | Tray app, hotkey wiring, worker orchestration                          |
| [clipboard.py](./src/lamarck_translator/clipboard.py)                 | Selection capture: four-method copy escalation, clipboard save/restore  |
| [screenshot.py](./src/lamarck_translator/screenshot.py)               | Full-screen overlay, drag selection, DPI-correct crop                   |
| [backend.py](./src/lamarck_translator/backend.py)                     | `codex.exe` discovery and the sandboxed `codex exec` call               |
| [prompts.py](./src/lamarck_translator/prompts.py)                     | Prompt construction for text and image input                            |
| [translation_pairs.py](./src/lamarck_translator/translation_pairs.py) | Parsing the structured response into sentence pairs                     |
| [result_window.py](./src/lamarck_translator/result_window.py)         | Frameless result window, bilingual sentence cards, paired hover         |
| [identity.py](./src/lamarck_translator/identity.py)                   | Signed-in Codex account, read from the local `auth.json` ID token       |
| [hotkeys.py](./src/lamarck_translator/hotkeys.py)                     | Global hotkeys via `RegisterHotKey` and `WM_HOTKEY`                     |
| [config.py](./src/lamarck_translator/config.py)                       | Configuration file loading and saving                                   |
| [worker.py](./src/lamarck_translator/worker.py)                       | Background translation task, temporary screenshot cleanup               |
| [history.py](./src/lamarck_translator/history.py)                     | The last five translations, their state, and the in-flight cap          |
| [tests/](./tests/)                                                    | 59 pytest tests                                                         |
| [build.ps1](./build.ps1)                                              | PyInstaller packaging script                                            |

---

## Installation

Requires **Windows 10/11**, **Python 3.10+**, and the **Codex CLI** installed on the machine.

```powershell
cd F:\VScode\LamarckCC\040_Lamarck_Translator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
codex login
python -m lamarck_translator
```

Or simply:

```powershell
.\run.ps1
```

Run `codex login` once before first use. Codex CLI accepts either a ChatGPT login or an API key; this app only invokes the CLI and never reads or writes its credential files.

## Usage

**Selection translation**

1. Select English text in a browser, in Zotero, or in most apps that can copy text.
2. Press `Alt+C`.
3. The app presses `Ctrl+C` for you, restores your previous clipboard, and shows the full sentence-by-sentence translation.
4. Hover over any English or Chinese sentence and its counterpart highlights with it.
5. Hold Ctrl and turn the wheel over the sentences to resize them; the size is kept for later translations and across restarts.

**Screenshot translation**

1. Put the mouse on the target screen and press `Alt+S`.
2. Hold the left button and drag a box over the content.
3. Release to submit, or press `Esc` to cancel.

**While you read**

Sending a translation never takes the screen away from a finished one you are reading. It opens a tab above the text and translates behind it, and marks that tab with a dot when the result lands, so you can finish the passage you are on first. Up to three translations run at once, and the last five stay reachable: click a tab to go back to one, with its green read-marks and scroll position where you left them.

The sun and moon button in the title bar switches between the light and dark themes. By default the window follows the Windows setting and keeps following it; pressing the button pins a theme instead, and setting `theme` back to `system` in the configuration file restores the following behaviour.

The tray menu triggers the same two actions, and can also check the Codex login status or quit the app. The window title area shows the OpenAI account the local Codex CLI is currently signed in as; after switching accounts it refreshes on the next translation. The line above it names the model and reasoning effort every translation runs with, exactly as they are passed to Codex; change them in the configuration file.

> **Tip:** some apps are slow to fill the clipboard with large selections. Raise `clipboard_wait_ms` if `Alt+C` comes back empty on long passages.

## Configuration

Created on first launch at:

```text
%APPDATA%\LamarckTranslator\config.json
```

| Key                 | Default                      | Description                                                                    |
| :------------------ | :--------------------------- | :------------------------------------------------------------------------------ |
| `text_hotkey`       | `Alt+C`                      | Selection-translation shortcut                                                 |
| `screenshot_hotkey` | `Alt+S`                      | Screenshot-translation shortcut                                                |
| `model`             | `gpt-5.6-sol`                | Passed to `codex exec --model`; leave empty to use the current Codex default   |
| `reasoning_effort`  | `high`                       | Sets `model_reasoning_effort`; leave empty to omit it                          |
| `timeout_seconds`   | `120`                        | Give up if Codex has not answered by then                                      |
| `clipboard_wait_ms` | `220`                        | How long to wait for the source app to fill the clipboard                      |
| `restore_clipboard` | `true`                       | Put the original clipboard contents back after capture                         |
| `pair_font_size`    | `15`                         | Sentence-text size in pixels; also set by Ctrl + wheel, which saves it here    |
| `theme`             | `system`                     | `system`, `light` or `dark`; the title-bar button writes the last two here     |
| `prompt`            | technical-translation style  | Translation style only; the structured-output format is appended automatically |

Shortcuts take the form `Modifier+Key`, where the modifiers are `Ctrl` / `Alt` / `Shift` / `Win` and the key is a single letter or digit, or `F1`–`F24`. Restart the app after editing the file, except for `pair_font_size` and `theme`, which the window writes itself.

## Packaging

```powershell
python -m pip install -e ".[dev]"
.\build.ps1
```

The result is a one-folder build at `dist\LamarckTranslator\LamarckTranslator.exe`. The packaged app still requires `codex.exe` to be present and signed in on the machine — it bundles the front end, not the backend.

## Privacy and Security

- Selected text and screenshots are sent to the Codex service the machine is signed in to.
- Nothing is logged: no source text, no translations, no screenshot history. Screenshots are written to the system temp directory and deleted as soon as the request returns.
- The account display reads only the `email` and `name` claims from the ID token in the local Codex `auth.json`. Access tokens, refresh tokens, and API keys are never displayed, stored, or transmitted.
- Each translation runs under a read-only sandbox in a temporary empty directory, in an ephemeral session.
- Do not commit the Codex login cache, an API key, or a configuration file that contains one.

## Known Limitations

- Selection mode works by copying, so the few apps that block copying cannot be read this way. Use screenshot mode there instead.
- The clipboard is restored by cloning the MIME data Qt can see; an app's private clipboard formats may not survive the round trip.
- Screenshot mode captures one screen per selection. A box spanning two monitors is not supported.
- If a shortcut is already taken by another app, registration fails at startup and the app reports it.

---

##### Translation runs on the [Codex CLI](https://github.com/openai/codex), which must be installed and signed in on the machine.
