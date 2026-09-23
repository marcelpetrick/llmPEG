# llmPEG local prototype

This localhost-only Web UI makes the totally lossy round trip visible:

```text
source image -> local Ollama/Qwen vision -> editable .llmpeg prompt
             -> local ComfyUI/Qwen-Image-2.1 -> new image -> experimental rating
```

The generator never receives the source image. The rating step receives both images, but sends
them only to the configured Ollama endpoint. There is no hosted generator or fallback path.

## Prerequisites

Install the project and pull the local vision model:

```bash
uv sync --extra dev
ollama pull qwen3.5:4b
```

ComfyUI must be reachable at `http://127.0.0.1:8188` with these Qwen-Image-2.1 files installed:

- `models/diffusion_models/qwen_image_2.1_int8_convrot.safetensors`
- `models/text_encoders/qwen3vl_8b_w4a8.safetensors`
- `models/vae/qwen_image_2.1_vae_bf16.safetensors`

The bundled API workflow uses native ComfyUI nodes, 30 Euler/simple steps, CFG 3.5, CPU int8
cache, and seed 42. Start the known local setup with
`../codingWithGPT/qwenImage2.1/serve.sh`, or start an equivalent ComfyUI checkout yourself.
The installed Qwen-Image-2.1 weights use the non-commercial Qwen Research licence; llmPEG does
not redistribute them.

## Run

```bash
uv run python prototypeWebUI/server.py \
  --vision-host http://127.0.0.1:11434
```

Open <http://127.0.0.1:8000>. The explicit loopback flag is useful when an old
`OLLAMA_VISION_HOST` is present in the shell. The backend binds to loopback, has no authentication,
and must not be exposed to a network.

The page defaults to the `detailed` profile. It shows the canonical JSON and gzip sizes side by
side, keeps the generated prompt editable, supports a square resolution and seed, and automatically
runs the experimental comparison after generation.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_VISION_HOST` / `--vision-host` | `http://127.0.0.1:11434` | image encoder and similarity rater |
| `LLMPEG_MODEL` | `qwen3.5:4b` | local vision-capable Ollama model |
| `LLMPEG_COMFYUI_HOST` | `http://127.0.0.1:8188` | local Qwen-Image-2.1 service |
| `LLMPEG_TIMEOUT` | `1200` seconds | total upstream request/generation bound |
| `LLMPEG_RATING_REPEATS` | `3` | repeated semantic judgments, maximum 5 |

Encoding releases the Ollama model when it finishes. Generation retrieves and validates the PNG,
then calls ComfyUI's `/free` endpoint. The last rating judgment releases Ollama again. This explicit
handoff lets both models share an 8 GB GPU instead of relying on a long idle timeout. The prototype
serializes encode, generate, and rate calls so concurrent HTTP requests cannot make the two model
runtimes fight over that GPU.

## API

| Route | Contract |
| --- | --- |
| `GET /api/config` | configured model, local generator identity, and ComfyUI reachability |
| `POST /api/encode?profile=detailed` | raw image bytes in; artifact, prompt, and plain/gzip measurements out |
| `POST /api/generate` | `{prompt,width,height,seed}` in; validated generated image bytes out |
| `POST /api/rate` | base64 source/reconstruction plus prompt and critical text in; metric vector out |

Uploads are bounded to 40 MiB and 50 megapixels, prompts to 20,000 characters, rating images to
40 MiB each, and generation to square multiples of 16 from 256 through 1536 pixels. The browser
can also open `index.html` directly; the server permits only the `Origin: null` API case needed by
that page.

## What the rating means

The report keeps deterministic layout/palette/edge proxies separate from repeated local Qwen
ratings of subject, identity, composition, text, and style. It exposes medians, spreads, concrete
differences, and prompt suggestions. It is not calibrated against human ratings and cannot prove
that two images are equivalent. See [`../docs/local-model-plan.md`](../docs/local-model-plan.md)
and [`../docs/metrics.md`](../docs/metrics.md).

On 2026-09-22 the live acceptance run exercised all four routes with `qwen3.5:4b`, ComfyUI 0.37.0,
and Qwen-Image-2.1. `/api/generate` returned a valid 256×256 PNG with the concrete generator header;
the rating completed three trials. The audited 512-pixel creator/rater run and its freely licensed
source credit are checked in under [`../docs/creator-rater/`](../docs/creator-rater/).

The tests are offline. They inject provider responses and never require a GPU, model, network,
credential, or running service.
