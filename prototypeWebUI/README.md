# llmPEG prototype web UI

Drop a photo in a browser, watch a vision model write it down, read the description it produced,
then have an image model paint a new picture from those words alone.

It is the whole llmPEG thesis in one page, and the point lands harder when you do it to your own
photo than when you read a table of numbers.

```text
your photo ──▶ downscale (Pillow LANCZOS) ──▶ Qwen3-VL on your Ollama box ──▶ ~1 KB of text
                                                                                    │
                                        a NEW image ◀── free image generator ◀───────┘
```

## Quick start

```bash
export OLLAMA_VISION_HOST=http://your-ollama-host:11434
uv run python prototypeWebUI/server.py
# open http://127.0.0.1:8000
```

Drag an image in (or click, or paste from the clipboard), pick a fidelity profile, press
**Analyze image**, wait, then press **Generate image**. The prompt box is editable before you
generate — that is the one genuinely nice property of a codec whose compressed form is readable
text.

## About that "free Google image API"

There isn't one. Google has no free, keyless, prompt-in-the-URL image endpoint. The service you
are remembering is almost certainly **[Pollinations](https://pollinations.ai/)**, which does work
exactly like that:

```
https://image.pollinations.ai/prompt/<url-encoded prompt>?width=1024&height=1024&seed=42
```

No API key, no account, no credits. That is the default generator here, and it is verified
working — the round trip below was produced with it.

The backend proxies that call rather than putting the URL straight into an `<img>` tag, so the
same code path can serve a local generator, and so a failure produces a readable error instead of
a broken image icon.

## Options for generation, cheapest effort first

| Option | Effort | Cost | Speed | Quality | Privacy |
| --- | --- | --- | --- | --- | --- |
| **Pollinations** (default) | none — already works | free | ~3 s | good | **prompt leaves your machine** |
| **Codex CLI** (`codex`) | none if you are logged in | uses your ChatGPT quota | ~40 s | best of the three | prompt goes to OpenAI |
| Local Stable Diffusion (A1111/Forge) | hours of setup, ~4–8 GB VRAM | free after setup | varies | very good, controllable | fully local |
| ComfyUI | more setup, node graphs | free after setup | varies | best control | fully local |

**The recommendation:** stay on Pollinations for casual use — it is instant and costs nothing.
Switch to `codex` when you want the best result and do not mind spending quota; it produced every
reconstruction in the expanded benchmark. Move to local Stable Diffusion when the prompt content
itself is sensitive, since that is the only option that keeps descriptions on your own hardware.

```bash
export LLMPEG_GENERATOR=codex      # verified working
```

Codex is an agent, not an image API, so this hands it a directory containing only `prompt.txt` and
asks it to save `out.png`. That isolation is deliberate: it is the same method the benchmark uses
to guarantee the generator never sees the source image.

You already run a GPU box for Ollama, so a local generator is a realistic next step:

```bash
# Automatic1111 with the API enabled
./webui.sh --api --listen
export LLMPEG_GENERATOR=local
export LLMPEG_SD_HOST=http://your-gpu-host:7860
```

`generate_local()` speaks the Automatic1111 `/sdapi/v1/txt2img` protocol, which Forge and several
others also implement. **It is the one unverified path**: no Stable Diffusion server was reachable
while this was written. Pollinations and Codex have both actually run through this server.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_VISION_HOST` | *(required)* | your Ollama endpoint |
| `LLMPEG_MODEL` | `qwen3-vl:32b-ctx49k` | vision model |
| `LLMPEG_GENERATOR` | `pollinations` | `pollinations`, `codex`, or `local` |
| `LLMPEG_SD_HOST` | `http://127.0.0.1:7860` | Automatic1111-compatible server |
| `LLMPEG_TIMEOUT` | `600` | seconds |

`--host` and `--port` are flags; the default bind is `127.0.0.1:8000`.

## What actually happened when this was tested

One real run, `survey/sources/cat-on-grass.jpg`, `balanced` profile:

| Step | Result |
| --- | ---: |
| Uploaded | 799,983 bytes |
| Re-encoded for the model (1536 px long edge) | 544,589 bytes |
| Semantic artifact | **1,134 bytes** |
| Ratio | **480:1** |
| Encode time | ~29 s |
| Generation time | ~3 s |

The result was recognisably a tabby cat lying on green grass, and just as recognisably **a
different cat**. Which is the entire point.

Note the ratio is quoted against the *re-encoded* bytes the model actually saw, not the original
upload. Quoting it against the 800 KB original would inflate it to 705:1 by taking credit for a
plain JPEG resize.

## Endpoints

| Route | Purpose |
| --- | --- |
| `GET /` | the page |
| `GET /api/config` | model and generator currently configured |
| `POST /api/encode?profile=balanced` | raw image bytes in, JSON with prompt and stats out |
| `POST /api/generate` | `{prompt, width, height, seed}` in, JPEG out |

The upload is the raw file as the request body — no multipart parsing, which keeps the server
under 250 lines.

## Warnings

- **Your image goes to your Ollama host. Your prompt goes to Pollinations** unless you switch to
  a local generator. A description can carry private facts even though it is smaller than the
  photo.
- **Not hardened.** No auth, no CSRF protection, no rate limiting, binds to localhost. It is a
  prototype for one person on one laptop. Do not expose it to a network.
- **Nothing is stored.** The upload lives in a temporary directory for the duration of one encode
  and is deleted; results exist only in your browser tab. Reloading loses them.
- The uploaded original is never modified — llmPEG never touches your source file.
- No automated tests cover this directory. It is a prototype, like `scripts/`, not product
  surface; the codec it calls is what carries the test suite.
