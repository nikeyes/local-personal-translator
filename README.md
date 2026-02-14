# Personal Translator

Local ES↔EN translator using [TranslateGemma 12B 8-bit](https://huggingface.co/mlx-community/translategemma-12b-it-8bit) with MLX on Apple Silicon.

## Setup

```bash
uv sync
```

The first run downloads the model (~12.5 GB). Subsequent runs start in seconds.

## Usage

### Web Interface (Recommended)

```bash
uv run python main.py --serve
```

Open `http://127.0.0.1:8785` in your browser for a DeepL-style interface:
- Two-panel layout (input | output)
- Language selectors (ES/EN)
- Auto-translation as you type
- Copy button for translated text

### API Server

The server also provides a REST API. Translate with curl:

```bash
curl -s -X POST 'http://127.0.0.1:8785?src=es&tgt=en' -d 'Hola mundo'
```

### Keyboard shortcuts (macOS)

Install Automator Quick Actions for CMD+SHIFT+E (ES→EN) and CMD+SHIFT+I (EN→ES):

```bash
bash install_shortcuts.sh
```

Flow: select text → CMD+SHIFT+E → web interface opens with translation.

Features:
- Auto-starts server if not running
- Supports long texts via base64 encoding
- Shows translation time
- Visual feedback (translating/success/error states)
- Copy button and CMD+C support
- Clean URL after loading

To remove:

```bash
bash uninstall_shortcuts.sh
```

### Interactive mode

```bash
uv run python main.py
```

Commands: `/swap` switches direction, `/q` exits.
