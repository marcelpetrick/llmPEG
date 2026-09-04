# llmPEG prototype web UI

Drop a photo in a browser, watch a vision model write it down, read the description it produced,
then have an image model paint a new picture from those words alone.

It is the whole llmPEG thesis in one page, and the point lands harder when you do it to your own
photo than when you read a table of numbers.

```text
your photo ──▶ downscale ──▶ Qwen3-VL on your Ollama box ──▶ compact text prompt
                                                                        │
                         a NEW image ◀── configured generator ◀──────────┘
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
text. Choose Codex, ComfyUI, Pollinations, or an Automatic1111-compatible server beside the
generation controls. The page shows an expected generation time while it waits and the measured
elapsed time when the request finishes. It follows the operating-system color preference on first
load and offers a persistent light/dark toggle in the header.

## About hosted generation

Pollinations provides a prompt-in-the-URL image endpoint, but its current API requires a key. Get
one from [Pollinations](https://enter.pollinations.ai/) and keep it server-side:

```text
https://gen.pollinations.ai/image/<url-encoded-prompt>?model=flux&width=1024&height=1024&seed=42
```

```bash
export POLLINATIONS_API_KEY=your-key
uv run python prototypeWebUI/server.py --generator pollinations
```

The backend adds the bearer token and proxies the result, so the key never enters browser code. A
failed upstream request becomes a readable error instead of a broken image icon.

## Generation options

| Option | Requirement | Measured speed | Privacy |
| --- | --- | ---: | --- |
| **Codex CLI** (`codex`, default) | logged-in CLI | ~40 s | prompt goes to OpenAI |
| ComfyUI | sibling checkout and prepared shell script | 7.64 s warm smoke test | fully local |
| Pollinations | API key and credits | ~3 s on former endpoint | **prompt leaves your machine** |
| Local Stable Diffusion | Automatic1111-compatible API | not measured | fully local |

Codex is the default because it produced every reconstruction in the expanded benchmark. Use
ComfyUI or Automatic1111 when the prompt must stay local, and Pollinations when a lightweight
hosted API is preferable. Provider availability, pricing, and latency can change.

Codex is an agent, not an image API. The backend runs `codex exec` in an ephemeral directory that
contains only `prompt.txt`, explicitly invokes `$imagegen` in built-in-tool mode, and requires it
to save `out.png`. The image API fallback is forbidden, so this path uses the logged-in Codex
session and does not require `OPENAI_API_KEY`. The source image is absent from both the request and
the temporary working directory. The selected size is a target for Codex; the built-in tool may
choose a different supported pixel size, which the page reports beneath the generated image.

## ComfyUI through the local shell adapter

The `comfyui` option runs the existing sibling checkout's self-starting script:

```text
/home/mpetrick/repos/ComfyUI/generate_image.sh "prompt" output.png
```

By default, the backend discovers it as `../ComfyUI/generate_image.sh` relative to this repository.
Override that location when the repositories are elsewhere:

```bash
export LLMPEG_COMFYUI_SCRIPT=/path/to/ComfyUI/generate_image.sh
uv run python prototypeWebUI/server.py
```

The script checks `http://127.0.0.1:8188/system_stats`, starts ComfyUI if necessary, waits up to
two minutes for it, then runs the prepared Flux 2 Klein 4B workflow. That workflow controls output
size and seed, so the Web UI's size and seed fields do not override them for this backend.

If the script is missing or exits while the service remains unreachable, the backend falls back
to Codex. The result identifies Codex as the provider and the page displays the fallback. If the
service is reachable but its workflow fails, the error remains visible; Codex is not run a second
time.

A live smoke test against ComfyUI 0.34.0 generated a valid 768×768 PNG in 7.64 seconds with the
service already running. A second check through `POST /api/generate` returned another valid PNG
and identified `comfyui` as the provider. This is not a general latency claim. Exact prompts,
workflow, dimensions, byte counts, headers, and results are in
[`comfyui-smoke.json`](comfyui-smoke.json).

You already run a GPU box for Ollama, so a local generator is a realistic next step:

```bash
# Automatic1111 with the API enabled
./webui.sh --api --listen
export LLMPEG_GENERATOR=local
export LLMPEG_SD_HOST=http://your-gpu-host:7860
```

`generate_local()` speaks the Automatic1111 `/sdapi/v1/txt2img` protocol, which Forge and several
others also implement. **It is an unverified path**: no Stable Diffusion server was reachable
while this was written. Codex and the former keyless Pollinations endpoint were tested live; the
current authenticated Pollinations request is covered offline but still needs a live check.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_VISION_HOST` | *(required)* | your Ollama endpoint |
| `LLMPEG_MODEL` | `qwen3-vl:32b-ctx49k` | vision model |
| `LLMPEG_GENERATOR` | `codex` | `codex`, `comfyui`, `pollinations`, or `local` |
| `LLMPEG_COMFYUI_SCRIPT` | `../ComfyUI/generate_image.sh` | self-starting ComfyUI adapter |
| `LLMPEG_COMFYUI_HOST` | `http://127.0.0.1:8188` | service health-check URL |
| `POLLINATIONS_API_KEY` | *(required for Pollinations)* | server-side API key |
| `LLMPEG_SD_HOST` | `http://127.0.0.1:7860` | Automatic1111-compatible server |
| `LLMPEG_TIMEOUT` | `600` | seconds |

`LLMPEG_GENERATOR` and `--generator` also accept `comfyui`. The flag sets the initially selected
generator; the selector can change it for each request. `--host`, `--port`, and `--vision-host`
configure the prototype server, whose default bind is `127.0.0.1:8000`.

## What actually happened when this was tested

One real run, `survey/sources/cat-on-grass.jpg`, `balanced` profile:

| Step | Result |
| --- | ---: |
| Uploaded | 799,983 bytes |
| Re-encoded for the model (1536 px long edge) | 544,589 bytes |
| Semantic artifact | **1,341 bytes** |
| Ratio | **406:1** |
| Encode time | ~13 s (warm model) |
| Generation time | ~3 s (former Pollinations endpoint) / ~40 s (Codex) |

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
| `POST /api/generate` | `{generator, prompt, width, height, seed}` in, generated image bytes out; actual provider in `X-llmPEG-Generator` |

The upload is the raw file as the request body, avoiding a multipart parser and another runtime
dependency.

## Warnings

- **Your image goes to your Ollama host. Your prompt goes to the configured generator.** With
  Codex or Pollinations, it leaves your machine; with ComfyUI or local Stable Diffusion, it does
  not. A short description can still contain private facts.
- **Not hardened.** No auth, no CSRF protection, no rate limiting, binds to localhost. It is a
  prototype for one person on one laptop. Do not expose it to a network.
- **Nothing is stored.** The upload lives in a temporary directory for the duration of one encode
  and is deleted; results exist only in your browser tab. Reloading loses them.
- The uploaded original is never modified — llmPEG never touches your source file.
- Offline tests cover request validation, direct-file CORS, backend discovery, invalid images,
  Codex invocation, and Pollinations request assembly. Live provider checks remain manual.
