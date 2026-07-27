#!/usr/bin/env python3
"""
Generate images and text-to-video clips through a New API gateway.

Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

VERSION = "2.4.0"

DEFAULT_IMAGE_MODEL = "wan2.7-image-pro"
DEFAULT_VIDEO_MODEL = "happyhorse-1.1-t2v"

# Curated catalog (Aliyun Bailian Token Plan). set-model also accepts any
# custom model string for private gateways; these are the known-good entries.
IMAGE_MODELS = {
    "wan2.7-image-pro": "Wan 2.7 Pro — commercial-grade quality (default)",
    "wan2.7-image": "Wan 2.7 — standard quality, fewer credits",
    "qwen-image-2.0-pro": "Qwen Image 2.0 Pro — strong in-image text rendering",
    "qwen-image-2.0": "Qwen Image 2.0 — lightweight, fast",
}
VIDEO_MODELS = {
    "happyhorse-1.1-t2v": "Text-to-video (default)",
    "happyhorse-1.1-i2v": "Image-to-video — requires image input",
    "happyhorse-1.1-r2v": "Reference-to-video — requires reference input",
}
# Models that need non-text input; the prompt-only pipeline cannot drive them.
IMAGE_INPUT_REQUIRED = {"happyhorse-1.1-i2v", "happyhorse-1.1-r2v"}

CONFIG_DIR = Path.home() / ".gen-media"
CONFIG_FILE = CONFIG_DIR / "config.json"
SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_TIMEOUT = 1800
POLL_INTERVAL = 5


class GenMediaError(RuntimeError):
    """A user-facing generation error."""


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    image_model: str = DEFAULT_IMAGE_MODEL
    video_model: str = DEFAULT_VIDEO_MODEL


def normalize_base_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if not url:
        raise GenMediaError("Base URL cannot be empty.")
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        raise GenMediaError("Base URL must begin with http:// or https://.")

    # Users often copy an Anthropic-compatible endpoint rather than the gateway root.
    suffixes = (
        "/v1/messages",
        "/messages",
        "/v1/chat/completions",
        "/chat/completions",
        "/v1",
    )
    lowered = url.lower()
    for suffix in suffixes:
        if lowered.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
            break
    return url


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * max(4, len(key) - 8)}{key[-4:]}"


def validate_model_choice(kind: str, model: str) -> None:
    catalog = IMAGE_MODELS if kind == "image" else VIDEO_MODELS
    if kind == "video" and model in IMAGE_INPUT_REQUIRED:
        raise GenMediaError(
            f"{model} requires image input; this skill runs text-to-video only. "
            f"Use {DEFAULT_VIDEO_MODEL} instead."
        )
    if model not in catalog:
        print(
            f"WARNING: {model} is not in the curated {kind} catalog; "
            "saving it as a custom gateway model."
        )


def save_config(config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_url": config.base_url,
        "api_key": config.api_key,
        "image_model": config.image_model,
        "video_model": config.video_model,
    }
    CONFIG_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(CONFIG_DIR, stat.S_IRWXU)
        os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows ACLs are not controlled reliably through chmod.
        pass


def configure(args: argparse.Namespace) -> int:
    print("Configure Gen Media with your own New API credentials.")
    base_url = args.base_url or input("New API Base URL: ").strip()
    api_key = (
        args.api_key or getpass.getpass("New API API Key (input hidden): ").strip()
    )
    if not api_key:
        raise GenMediaError("API Key cannot be empty.")

    image_model = (args.image_model or DEFAULT_IMAGE_MODEL).strip()
    video_model = (args.video_model or DEFAULT_VIDEO_MODEL).strip()
    validate_model_choice("image", image_model)
    validate_model_choice("video", video_model)

    config = Config(normalize_base_url(base_url), api_key, image_model, video_model)
    save_config(config)
    print(f"Saved configuration to: {CONFIG_FILE}")
    print(f"Base URL: {config.base_url}")
    print(f"API Key: {mask_key(config.api_key)}")
    print(f"Image model: {config.image_model}")
    print(f"Video model: {config.video_model}")
    return 0


def load_config() -> Config:
    env_base = os.getenv("GEN_MEDIA_BASE_URL", "").strip()
    env_key = os.getenv("GEN_MEDIA_API_KEY", "").strip()
    if env_base and env_key:
        return Config(
            normalize_base_url(env_base),
            env_key,
            os.getenv("GEN_MEDIA_IMAGE_MODEL", "").strip() or DEFAULT_IMAGE_MODEL,
            os.getenv("GEN_MEDIA_VIDEO_MODEL", "").strip() or DEFAULT_VIDEO_MODEL,
        )

    if not CONFIG_FILE.exists():
        if sys.stdin.isatty():
            print("No Gen Media configuration found. Starting first-time setup.")
            configure(
                argparse.Namespace(
                    base_url=None,
                    api_key=None,
                    image_model=None,
                    video_model=None,
                )
            )
        else:
            raise GenMediaError(
                f"CONFIG_MISSING: no configuration at {CONFIG_FILE}. "
                "Ask the user for their Base URL and API Key right here in chat, "
                "then run: "
                f'python "{SCRIPT_PATH}" configure --base-url "<url>" --api-key "<key>" '
                "(the key passes through this chat once and is saved to the local "
                "config; for a no-chat alternative use the GEN_MEDIA_* env vars)."
            )

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenMediaError(f"Cannot read configuration: {exc}") from exc

    base_url = str(data.get("base_url", "")).strip()
    api_key = str(data.get("api_key", "")).strip()
    if not base_url or not api_key:
        raise GenMediaError(
            "Configuration is incomplete. Run 'gen_media.py configure' again."
        )
    image_model = str(data.get("image_model", "")).strip() or DEFAULT_IMAGE_MODEL
    video_model = str(data.get("video_model", "")).strip() or DEFAULT_VIDEO_MODEL
    return Config(normalize_base_url(base_url), api_key, image_model, video_model)


def show_config(_: argparse.Namespace) -> int:
    config = load_config()
    source = (
        "environment variables"
        if (os.getenv("GEN_MEDIA_BASE_URL") and os.getenv("GEN_MEDIA_API_KEY"))
        else str(CONFIG_FILE)
    )
    print(f"Configuration source: {source}")
    print(f"Base URL: {config.base_url}")
    print(f"API Key: {mask_key(config.api_key)}")
    print(f"Image model: {config.image_model}")
    print(f"Video model: {config.video_model}")
    return 0


def reset_config(_: argparse.Namespace) -> int:
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        print(f"Removed: {CONFIG_FILE}")
    else:
        print("No saved configuration exists.")
    return 0


def print_version(_: argparse.Namespace) -> int:
    print(f"gen-media {VERSION}")
    return 0


def list_models(_: argparse.Namespace) -> int:
    try:
        config = load_config()
        current_image, current_video = config.image_model, config.video_model
    except GenMediaError:
        current_image, current_video = DEFAULT_IMAGE_MODEL, DEFAULT_VIDEO_MODEL
        print("No configuration yet; showing defaults.\n")

    print("Image models:")
    for model, note in IMAGE_MODELS.items():
        marker = "*" if model == current_image else " "
        print(f" {marker} {model:<22} {note}")
    print("\nVideo models:")
    for model, note in VIDEO_MODELS.items():
        marker = "*" if model == current_video else " "
        suffix = (
            " [not usable: needs image input]" if model in IMAGE_INPUT_REQUIRED else ""
        )
        print(f" {marker} {model:<22} {note}{suffix}")
    print(
        "\n* = current selection. Switch with: set-model --image <model> / --video <model>"
    )
    return 0


def set_model(args: argparse.Namespace) -> int:
    if not args.image and not args.video:
        raise GenMediaError(
            "Pass --image <model> and/or --video <model>. Run list-models first."
        )
    config = load_config()
    image_model = config.image_model
    video_model = config.video_model
    if args.image:
        validate_model_choice("image", args.image)
        image_model = args.image
    if args.video:
        validate_model_choice("video", args.video)
        video_model = args.video
    save_config(Config(config.base_url, config.api_key, image_model, video_model))
    print(f"Image model: {image_model}")
    print(f"Video model: {video_model}")
    return 0


def request_json(
    method: str,
    url: str,
    config: Config,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    body = None
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Accept": "application/json",
        "User-Agent": f"gen-media-skill/{VERSION}",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        detail = raw.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            detail = extract_error_message(parsed) or detail
        except json.JSONDecodeError:
            pass
        raise GenMediaError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GenMediaError(f"Cannot connect to {url}: {exc.reason}") from exc

    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        preview = raw[:500].decode("utf-8", errors="replace")
        raise GenMediaError(f"Expected JSON from {url}, received: {preview}") from exc


def extract_error_message(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    error = data.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "")
    if isinstance(error, str):
        return error
    return str(data.get("message") or data.get("code") or "")


def iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def extract_urls(data: Any, keys: set[str]) -> list[str]:
    found: list[str] = []
    for obj in iter_dicts(data):
        for key, value in obj.items():
            if key.lower() in keys and isinstance(value, str):
                if value.startswith(("http://", "https://", "data:")):
                    found.append(value)
    # Preserve order while removing duplicates.
    return list(dict.fromkeys(found))


def safe_output_dir(value: str | None) -> Path:
    directory = Path(value).expanduser() if value else Path.cwd()
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def download_url(
    url: str,
    target: Path,
    config: Config | None = None,
    authenticated: bool = False,
    timeout: int = 300,
) -> Path:
    headers = {"User-Agent": f"gen-media-skill/{VERSION}"}
    if authenticated and config is not None:
        headers["Authorization"] = f"Bearer {config.api_key}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with target.open("wb") as file:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    file.write(chunk)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        if target.exists():
            target.unlink(missing_ok=True)
        raise GenMediaError(f"Failed to download media from {url}: {exc}") from exc

    if not target.exists() or target.stat().st_size == 0:
        raise GenMediaError(f"Downloaded file is empty: {target}")
    return target.resolve()


def write_data_url(value: str, target: Path) -> Path:
    try:
        header, encoded = value.split(",", 1)
    except ValueError as exc:
        raise GenMediaError("Invalid data URL returned by the image API.") from exc
    if ";base64" not in header:
        raise GenMediaError("Only base64 data URLs are supported.")
    try:
        target.write_bytes(base64.b64decode(encoded))
    except (ValueError, OSError) as exc:
        raise GenMediaError(f"Cannot decode image data: {exc}") from exc
    return target.resolve()


def generate_image(args: argparse.Namespace) -> int:
    config = load_config()
    output_dir = safe_output_dir(args.output_dir)
    model = args.model or config.image_model
    endpoint = f"{config.base_url}/v1/images/generations"
    payload = {
        "model": model,
        "prompt": args.prompt,
        "size": args.size,
        "n": args.count,
        "response_format": "url",
    }
    result = request_json(
        "POST", endpoint, config, payload, timeout=args.request_timeout
    )
    error_message = extract_error_message(result)
    if error_message and not result.get("data"):
        raise GenMediaError(error_message)

    urls = extract_urls(result, {"url", "image"})
    b64_values: list[str] = []
    data_items = result.get("data")
    if isinstance(data_items, list):
        for item in data_items:
            if isinstance(item, dict) and isinstance(item.get("b64_json"), str):
                b64_values.append(item["b64_json"])

    files: list[Path] = []
    index = 1
    for url in urls:
        suffix = ".png"
        target = output_dir / f"generated_image_{timestamp()}_{index}{suffix}"
        if url.startswith("data:"):
            files.append(write_data_url(url, target))
        else:
            files.append(download_url(url, target))
        index += 1

    for encoded in b64_values:
        target = output_dir / f"generated_image_{timestamp()}_{index}.png"
        try:
            target.write_bytes(base64.b64decode(encoded))
        except (ValueError, OSError) as exc:
            raise GenMediaError(f"Cannot decode b64_json image: {exc}") from exc
        files.append(target.resolve())
        index += 1

    if not files:
        preview = json.dumps(result, ensure_ascii=False)[:1000]
        raise GenMediaError(f"No image URL or image data found in response: {preview}")

    print("IMAGE_GENERATION_COMPLETED")
    print(f"MODEL={model}")
    for file in files:
        print(f"FILE={file}")
    return 0


def extract_task_id(result: dict[str, Any]) -> str:
    candidates = [
        result.get("id"),
        result.get("task_id"),
    ]
    data = result.get("data")
    if isinstance(data, dict):
        candidates.extend([data.get("id"), data.get("task_id")])
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    for obj in iter_dicts(result):
        for key in ("task_id", "id"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def status_snapshot(result: dict[str, Any]) -> tuple[str, str, str]:
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    status = str(data.get("status") or result.get("status") or "").strip()
    progress = str(data.get("progress") or result.get("progress") or "").strip()
    error = extract_error_message(data) or extract_error_message(result)
    if not error:
        error = str(
            data.get("fail_reason")
            or result.get("fail_reason")
            or data.get("reason")
            or ""
        ).strip()
    return status, progress, error


def is_completed(status: str) -> bool:
    return status.lower() in {"completed", "success", "succeeded", "done"}


def is_failed(status: str) -> bool:
    return status.lower() in {
        "failed",
        "failure",
        "canceled",
        "cancelled",
        "error",
        "unknown",
    }


def submit_video(
    config: Config,
    payload: dict[str, Any],
    timeout: int,
) -> tuple[str, str]:
    endpoints = [
        f"{config.base_url}/v1/videos",
        f"{config.base_url}/v1/video/generations",
    ]
    errors: list[str] = []
    for endpoint in endpoints:
        try:
            result = request_json("POST", endpoint, config, payload, timeout=timeout)
            task_id = extract_task_id(result)
            if not task_id:
                raise GenMediaError(
                    "Video submission succeeded but no task ID was returned: "
                    + json.dumps(result, ensure_ascii=False)[:1000]
                )
            return task_id, endpoint
        except GenMediaError as exc:
            errors.append(str(exc))
            if "HTTP 404" not in str(exc) and "HTTP 405" not in str(exc):
                raise
    raise GenMediaError(
        "Neither New API video route is available:\n" + "\n".join(errors)
    )


def poll_video(
    config: Config,
    task_id: str,
    submit_endpoint: str,
    timeout: int,
) -> dict[str, Any]:
    if submit_endpoint.endswith("/v1/videos"):
        poll_url = f"{config.base_url}/v1/videos/{urllib.parse.quote(task_id)}"
    else:
        poll_url = (
            f"{config.base_url}/v1/video/generations/{urllib.parse.quote(task_id)}"
        )

    deadline = time.monotonic() + timeout
    last_status = ""
    while time.monotonic() < deadline:
        result = request_json("GET", poll_url, config, timeout=120)
        status, progress, error = status_snapshot(result)
        printable = status or "processing"
        if progress:
            printable = f"{printable} ({progress})"
        if printable != last_status:
            print(f"VIDEO_STATUS={printable}", flush=True)
            last_status = printable
        if is_completed(status):
            return result
        if is_failed(status):
            raise GenMediaError(
                error or f"Video generation failed with status: {status}"
            )
        time.sleep(POLL_INTERVAL)

    raise GenMediaError(
        f"Video generation did not complete within {timeout} seconds. "
        f"Task ID: {task_id}"
    )


def generate_video(args: argparse.Namespace) -> int:
    config = load_config()
    model = args.model or config.video_model
    if model in IMAGE_INPUT_REQUIRED:
        raise GenMediaError(
            f"{model} requires image input; this skill runs text-to-video only. "
            f"Fix with: set-model --video {DEFAULT_VIDEO_MODEL}"
        )
    output_dir = safe_output_dir(args.output_dir)
    payload = {
        "model": model,
        "prompt": args.prompt,
        "duration": args.duration,
        "seconds": str(args.duration),
        "metadata": {
            "parameters": {
                "resolution": args.resolution,
                "ratio": args.ratio,
                "duration": args.duration,
                "prompt_extend": True,
                "watermark": False,
            }
        },
    }
    task_id, submit_endpoint = submit_video(config, payload, args.request_timeout)
    print(f"VIDEO_TASK_ID={task_id}", flush=True)

    result = poll_video(config, task_id, submit_endpoint, args.timeout)
    target = output_dir / f"generated_video_{timestamp()}.mp4"

    # Prefer New API's authenticated content proxy.
    content_url = f"{config.base_url}/v1/videos/{urllib.parse.quote(task_id)}/content"
    try:
        file = download_url(
            content_url,
            target,
            config=config,
            authenticated=True,
            timeout=600,
        )
    except GenMediaError as proxy_error:
        # Fall back to a direct result URL in the task payload.
        urls = extract_urls(result, {"url", "result_url", "video_url"})
        direct_urls = [url for url in urls if not url.startswith("data:")]
        if not direct_urls:
            raise GenMediaError(
                f"Task completed, but video download failed: {proxy_error}"
            ) from proxy_error
        file = download_url(direct_urls[0], target, timeout=600)

    print("VIDEO_GENERATION_COMPLETED")
    print(f"MODEL={model}")
    print(f"FILE={file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate images and videos through a user's New API gateway."
    )
    parser.add_argument("--version", action="version", version=f"gen-media {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    version_parser = subparsers.add_parser("version", help="Print the script version.")
    version_parser.set_defaults(func=print_version)

    config_parser = subparsers.add_parser("configure", help="Save New API credentials.")
    config_parser.add_argument("--base-url")
    config_parser.add_argument("--api-key")
    config_parser.add_argument("--image-model")
    config_parser.add_argument("--video-model")
    config_parser.set_defaults(func=configure)

    show_parser = subparsers.add_parser(
        "show-config", help="Show masked configuration."
    )
    show_parser.set_defaults(func=show_config)

    reset_parser = subparsers.add_parser(
        "reset-config", help="Remove saved configuration."
    )
    reset_parser.set_defaults(func=reset_config)

    list_parser = subparsers.add_parser(
        "list-models", help="List the curated model catalog and current selection."
    )
    list_parser.set_defaults(func=list_models)

    set_parser = subparsers.add_parser(
        "set-model", help="Persist the preferred image and/or video model."
    )
    set_parser.add_argument("--image")
    set_parser.add_argument("--video")
    set_parser.set_defaults(func=set_model)

    image_parser = subparsers.add_parser("image", help="Generate and download images.")
    image_parser.add_argument("--prompt", required=True)
    image_parser.add_argument("--size", default="2048x2048")
    image_parser.add_argument("--count", type=int, default=1, choices=range(1, 5))
    image_parser.add_argument("--model", help="One-off model override.")
    image_parser.add_argument("--output-dir")
    image_parser.add_argument("--request-timeout", type=int, default=300)
    image_parser.set_defaults(func=generate_image)

    video_parser = subparsers.add_parser("video", help="Generate and download a video.")
    video_parser.add_argument("--prompt", required=True)
    video_parser.add_argument(
        "--resolution",
        default="1080P",
        choices=("720P", "1080P"),
    )
    video_parser.add_argument(
        "--ratio",
        default="16:9",
        choices=("16:9", "9:16", "1:1", "4:3", "3:4"),
    )
    video_parser.add_argument("--duration", type=int, default=5, choices=range(3, 16))
    video_parser.add_argument("--model", help="One-off model override.")
    video_parser.add_argument("--output-dir")
    video_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    video_parser.add_argument("--request-timeout", type=int, default=300)
    video_parser.set_defaults(func=generate_video)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except GenMediaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
