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

The served URL is the simplest option. Opening `prototypeWebUI/index.html` directly also works:
when loaded through `file://`, the page sends API requests to the backend at
`http://127.0.0.1:8000`. The Python backend must still be running because it validates artifacts,
downscales uploads, and proxies Ollama and the image generator.

The Ollama endpoint can also be supplied without exporting an environment variable:

```bash
uv run python prototypeWebUI/server.py --vision-host http://your-ollama-host:11434
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

No API key, no account, no credits. It remains available as an opt-in alternative, and the round
trip below was produced with it.

The backend proxies that call rather than putting the URL straight into an `<img>` tag, so the
same code path can serve a local generator, and so a failure produces a readable error instead of
a broken image icon.

## Options for generation, cheapest effort first

| Option | Effort | Cost | Speed | Quality | Privacy |
| --- | --- | --- | --- | --- | --- |
| Pollinations | none — already works | free | ~3 s | good | **prompt leaves your machine** |
| **Codex CLI** (`codex`, default) | none if you are logged in | uses your ChatGPT quota | ~40 s | best of the three | prompt goes to OpenAI |
| Local Stable Diffusion (A1111/Forge) | hours of setup, ~4–8 GB VRAM | free after setup | varies | very good, controllable | fully local |
| ComfyUI | more setup, node graphs | free after setup | varies | best control | fully local |

Codex is the default because it produced every reconstruction in the expanded benchmark. Use
Pollinations when speed and no-account access matter more, or local Stable Diffusion when the
prompt content itself is sensitive.

```bash
uv run python prototypeWebUI/server.py --generator pollinations
```

Codex is an agent, not an image API. The backend runs `codex exec` in an ephemeral directory that
contains only `prompt.txt`, explicitly invokes `$imagegen` in built-in-tool mode, and requires it
to save `out.png`. The image API fallback is forbidden, so this path uses the logged-in Codex
session and does not require `OPENAI_API_KEY`. The source image is absent from both the request and
the temporary working directory. The selected size is a target for Codex; the built-in tool may
choose a different supported pixel size, which the page reports beneath the generated image.

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
| `LLMPEG_GENERATOR` | `codex` | `codex`, `pollinations`, or `local` |
| `LLMPEG_SD_HOST` | `http://127.0.0.1:7860` | Automatic1111-compatible server |
| `LLMPEG_TIMEOUT` | `600` | seconds |

`--host`, `--port`, `--vision-host`, and `--generator` are flags; the default bind is
`127.0.0.1:8000`.

## What actually happened when this was tested

One real run, `survey/sources/cat-on-grass.jpg`, `balanced` profile:

| Step | Result |
| --- | ---: |
| Uploaded | 799,983 bytes |
| Re-encoded for the model (1536 px long edge) | 544,589 bytes |
| Semantic artifact | **1,341 bytes** |
| Ratio | **406:1** |
| Encode time | ~13 s (warm model) |
| Generation time | ~3 s (Pollinations) / ~40 s (Codex) |

The result was recognisably a tabby cat lying on green grass, and just as recognisably **a
different cat**. Which is the entire point.

Note the ratio is quoted against the *re-encoded* bytes the model actually saw, not the original
upload. Quoting it against the 800 KB original would inflate it to 597:1 by taking credit for a
plain JPEG resize. The artifact includes the 228-byte format header
([`docs/format.md`](../docs/format.md)); encode time varies with how warm the model is.

## Endpoints

| Route | Purpose |
| --- | --- |
| `GET /` | the page |
| `GET /api/config` | model and generator currently configured |
| `POST /api/encode?profile=balanced` | raw image bytes in, JSON with prompt and stats out |
| `POST /api/generate` | `{prompt, width, height, seed}` in, JPEG out |

The upload is the raw file as the request body, avoiding a multipart parser and another runtime
dependency.

## Warnings

- **Your image goes to your Ollama host. Your prompt goes to Pollinations** unless you switch to
  a local generator. A description can carry private facts even though it is smaller than the
  photo.
- **Not hardened.** No auth, no CSRF protection, no rate limiting, binds to localhost. It is a
  prototype for one person on one laptop. Do not expose it to a network.
- **Nothing is stored.** The upload lives in a temporary directory for the duration of one encode
  and is deleted; results exist only in your browser tab. Reloading loses them.
- The uploaded original is never modified — llmPEG never touches your source file.
- Offline tests cover request validation, direct-file CORS, backend discovery, and invalid image
  handling. Ollama and generator integrations remain manual checks.
