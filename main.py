import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

MODEL = "mlx-community/translategemma-12b-it-8bit"
PORT = 8785
STATIC_DIR = Path(__file__).parent

# Content-Type mapping for static files
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}

sampler = make_sampler(temp=0.0)


def build_prompt(tokenizer, src: str, tgt: str, text: str) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "source_lang_code": src,
                    "target_lang_code": tgt,
                    "text": text,
                }
            ],
        }
    ]
    return tokenizer.apply_chat_template(messages, add_generation_prompt=True)


def translate(model, tokenizer, src: str, tgt: str, text: str) -> str:
    # IMPORTANT: These values must match client-side validation in app.js
    MAX_TEXT_LENGTH = 5000
    SUPPORTED_LANGS = {'en', 'es'}

    # Validate inputs
    if src not in SUPPORTED_LANGS or tgt not in SUPPORTED_LANGS:
        raise ValueError(f"Unsupported language pair: {src} -> {tgt}. Supported: {SUPPORTED_LANGS}")

    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Text too long: {len(text)} characters (max {MAX_TEXT_LENGTH})")

    if not text.strip():
        raise ValueError("Text cannot be empty")

    try:
        prompt = build_prompt(tokenizer, src, tgt, text)
        result = generate(model, tokenizer, prompt=prompt, max_tokens=512, sampler=sampler)
        return result
    except MemoryError:
        print(f"ERROR: Out of memory translating {len(text)} chars", file=sys.stderr)
        raise ValueError("Text too long, please try shorter text")
    except Exception as e:
        print(f"ERROR: Translation failed: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"  src={src}, tgt={tgt}, text_len={len(text)}", file=sys.stderr)
        raise


def load_model():
    print("Loading model...", file=sys.stderr)

    try:
        model, tokenizer = load(MODEL)
    except FileNotFoundError as e:
        print(f"ERROR: Model not found at {MODEL}", file=sys.stderr)
        print("First run downloads ~12.5GB. Check network connection.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)
    except MemoryError:
        print("ERROR: Insufficient memory to load model", file=sys.stderr)
        print("This model requires approximately 12GB RAM", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load model: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        end_of_turn_id = tokenizer.encode("<end_of_turn>", add_special_tokens=False)[-1]
        tokenizer._eos_token_ids.add(end_of_turn_id)  # MLX community model misses this stop token
    except (IndexError, AttributeError) as e:
        print(f"ERROR: Failed to configure tokenizer: {e}", file=sys.stderr)
        print("The model may be incompatible or corrupted", file=sys.stderr)
        sys.exit(1)

    print("Model ready.", file=sys.stderr)
    return model, tokenizer


def serve(model, tokenizer):
    class Handler(BaseHTTPRequestHandler):
        def send_cors_headers(self):
            """Add CORS headers to allow cross-origin requests"""
            self.send_header("Access-Control-Allow-Origin", "*")

        def do_GET(self):
            # Serve static files
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/" or path == "/index.html":
                file_path = STATIC_DIR / "index.html"
            elif path == "/styles.css":
                file_path = STATIC_DIR / "styles.css"
            elif path == "/app.js":
                file_path = STATIC_DIR / "app.js"
            else:
                self.send_response(404)
                self.end_headers()
                return

            try:
                content = file_path.read_bytes()
                self.send_response(200)

                # Set Content-Type based on file extension
                content_type = CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")
                self.send_header("Content-Type", content_type)

                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                print(f"ERROR: File not found: {file_path}", file=sys.stderr)
                print(f"  Request path: {path}", file=sys.stderr)
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            try:
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                # Translation API
                if "src" not in params or "tgt" not in params:
                    self.send_response(400)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(b"Missing src/tgt query params. Use: POST /?src=es&tgt=en")
                    return

                src = params["src"][0]
                tgt = params["tgt"][0]

                # Read and decode request body with error handling
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    text = self.rfile.read(content_length).decode('utf-8')
                except (ValueError, UnicodeDecodeError) as e:
                    print(f"ERROR: Invalid request body: {e}", file=sys.stderr)
                    self.send_response(400)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(f"Invalid request body: {e}".encode())
                    return

                print(f"[{src}->{tgt}] {text[:100]}{'...' if len(text) > 100 else ''}", file=sys.stderr)

                # Translate with error handling
                try:
                    result = translate(model, tokenizer, src, tgt, text)
                except ValueError as e:
                    # Expected validation errors
                    print(f"ERROR: Validation failed: {e}", file=sys.stderr)
                    self.send_response(400)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(str(e).encode())
                    return
                except Exception as e:
                    # Unexpected errors
                    print(f"ERROR: Translation failed unexpectedly: {type(e).__name__}: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(b"Internal server error during translation")
                    return

                print(f"       -> {result[:100]}{'...' if len(result) > 100 else ''}", file=sys.stderr)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(result.encode())

            except Exception as e:
                # Catch-all for any unhandled errors
                print(f"ERROR: Unhandled exception in do_POST: {type(e).__name__}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                try:
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(b"Internal server error")
                except Exception:
                    pass  # Already in error state, can't send response

        def do_OPTIONS(self):
            # Handle CORS preflight
            self.send_response(200)
            self.send_cors_headers()
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, _format, *_args):
            pass

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Serving on http://127.0.0.1:{PORT}", file=sys.stderr)
    server.serve_forever()


def repl(model, tokenizer):
    print("Type text to translate (es->en). /swap to switch. /q to quit.\n", file=sys.stderr)
    src, tgt = "es", "en"

    while True:
        try:
            line = input(f"[{src}->{tgt}] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line.lower() in ("/q", "/quit"):
            break
        if line.lower() == "/swap":
            src, tgt = tgt, src
            continue

        print(translate(model, tokenizer, src, tgt, line))
        print()


def main():
    model, tokenizer = load_model()

    if "--serve" in sys.argv:
        serve(model, tokenizer)
    else:
        repl(model, tokenizer)


if __name__ == "__main__":
    main()
