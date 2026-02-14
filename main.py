import gc
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import mlx.core as mx
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

MODELS = {
    "8bit": "mlx-community/translategemma-12b-it-8bit",
    "4bit": "mlx-community/translategemma-12b-it-4bit",
}
PORT = 8785
STATIC_DIR = Path(__file__).parent

# Content-Type mapping for static files
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}

sampler = make_sampler(temp=0.0)

# Global state for current model
current_model = None
current_tokenizer = None
current_model_name = None


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


def translate(model, tokenizer, src: str, tgt: str, text: str) -> tuple[str, float]:
    """Translate text and return (result, elapsed_time_seconds)"""
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

        start = time.perf_counter()
        result = generate(model, tokenizer, prompt=prompt, max_tokens=512, sampler=sampler)
        elapsed = time.perf_counter() - start

        return result, elapsed
    except MemoryError:
        print(f"ERROR: Out of memory translating {len(text)} chars", file=sys.stderr)
        raise ValueError("Text too long, please try shorter text")
    except Exception as e:
        print(f"ERROR: Translation failed: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"  src={src}, tgt={tgt}, text_len={len(text)}", file=sys.stderr)
        raise


def load_model(model_name: str):
    """Load model by name (8bit or 4bit)"""
    model_path = MODELS.get(model_name)
    if not model_path:
        print(f"ERROR: Unknown model '{model_name}'. Available: {list(MODELS.keys())}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {model_name} model: {model_path}...", file=sys.stderr)

    try:
        model, tokenizer = load(model_path)
    except FileNotFoundError as e:
        print(f"ERROR: Model not found at {model_path}", file=sys.stderr)
        print(f"First run downloads model. Check network connection.", file=sys.stderr)
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

    print(f"Model ready ({model_name}).", file=sys.stderr)
    return model, tokenizer


def serve(model, tokenizer, model_name: str):
    global current_model, current_tokenizer, current_model_name
    current_model = model
    current_tokenizer = tokenizer
    current_model_name = model_name

    class Handler(BaseHTTPRequestHandler):
        def send_cors_headers(self):
            """Add CORS headers to allow cross-origin requests"""
            self.send_header("Access-Control-Allow-Origin", "*")

        def do_GET(self):
            # Serve static files
            parsed = urlparse(self.path)
            path = parsed.path

            # API endpoint to get current model
            if path == "/api/model":
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_cors_headers()
                self.end_headers()
                import json
                response = json.dumps({"model": current_model_name})
                self.wfile.write(response.encode())
                return

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
            global current_model, current_tokenizer, current_model_name

            try:
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                # API endpoint to change model
                if parsed.path == "/api/model":
                    try:
                        content_length = int(self.headers.get("Content-Length", 0))
                        body = self.rfile.read(content_length).decode('utf-8')
                        import json
                        data = json.loads(body)
                        new_model_name = data.get("model")

                        if new_model_name not in MODELS:
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.send_cors_headers()
                            self.end_headers()
                            error_response = json.dumps({
                                "error": f"Invalid model: {new_model_name}",
                                "available": list(MODELS.keys())
                            })
                            self.wfile.write(error_response.encode())
                            return

                        if new_model_name == current_model_name:
                            # Model already loaded
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.send_cors_headers()
                            self.end_headers()
                            response = json.dumps({"model": current_model_name, "status": "already_loaded"})
                            self.wfile.write(response.encode())
                            return

                        # Free current model before loading new one
                        print(f"\nSwitching to {new_model_name} model...", file=sys.stderr)
                        current_model = None
                        current_tokenizer = None
                        gc.collect()
                        mx.metal.clear_cache()

                        new_model, new_tokenizer = load_model(new_model_name)
                        current_model = new_model
                        current_tokenizer = new_tokenizer
                        current_model_name = new_model_name

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_cors_headers()
                        self.end_headers()
                        response = json.dumps({"model": current_model_name, "status": "loaded"})
                        self.wfile.write(response.encode())
                        return

                    except json.JSONDecodeError as e:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_cors_headers()
                        self.end_headers()
                        error_response = json.dumps({"error": f"Invalid JSON: {e}"})
                        self.wfile.write(error_response.encode())
                        return

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

                # Translate with error handling (use current model)
                try:
                    result, elapsed = translate(current_model, current_tokenizer, src, tgt, text)
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

                print(f"       -> {result[:100]}{'...' if len(result) > 100 else ''} ({elapsed:.2f}s)", file=sys.stderr)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("X-Translation-Time", f"{elapsed:.3f}")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Expose-Headers", "X-Translation-Time")
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


def repl(model, tokenizer, model_name: str):
    print(f"Type text to translate (es->en). /swap to switch. /q to quit. (Using {model_name})\n", file=sys.stderr)
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

        result, elapsed = translate(model, tokenizer, src, tgt, line)
        print(result)
        print(f"({elapsed:.2f}s)", file=sys.stderr)
        print()


def main():
    # Parse model selection argument
    model_name = "8bit"  # Default
    for arg in sys.argv[1:]:
        if arg in ("--4bit", "-4"):
            model_name = "4bit"
        elif arg in ("--8bit", "-8"):
            model_name = "8bit"

    model, tokenizer = load_model(model_name)

    if "--serve" in sys.argv:
        serve(model, tokenizer, model_name)
    else:
        repl(model, tokenizer, model_name)


if __name__ == "__main__":
    main()
