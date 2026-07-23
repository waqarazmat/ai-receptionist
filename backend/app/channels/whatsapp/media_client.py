"""Meta Graph API media operations for WhatsApp voice notes.

Handles the two directions:
  - Inbound: resolve a media_id to a download URL, then stream the binary
    to a local file (download_voice_note).
  - Outbound: upload a synthesised audio file and get back a media_id that
    can be referenced in a send-audio-message API call (upload_voice_reply).

Kept separate from message_sender.py because these are multipart binary
transfers with their own error surface and size/type constraints.
"""

import uuid
from pathlib import Path

import httpx
import structlog

from app.channels.whatsapp.message_sender import (
    GRAPH_API_BASE,
    REQUEST_TIMEOUT_SECONDS,
    WhatsAppCredentialsError,
    _post_message,
    get_credentials,
)

logger = structlog.get_logger()

# Meta allows up to 16 MB for audio media uploads.
_DOWNLOAD_TIMEOUT_SECONDS = 60.0
_UPLOAD_TIMEOUT_SECONDS = 60.0


class MediaDownloadError(Exception):
    """Could not resolve or download a Meta media asset."""


class MediaUploadError(Exception):
    """Could not upload audio to Meta's media servers."""


async def _resolve_media_metadata(media_id: str, access_token: str) -> dict:
    """Call GET /{media_id} and return the full metadata dict.

    Meta returns: url, mime_type, sha256, file_size (bytes), id.
    The URL is short-lived — download immediately after calling this.
    """
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(
            f"{GRAPH_API_BASE}/{media_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code != 200:
        raise MediaDownloadError(
            f"Failed to resolve media_id={media_id}: "
            f"HTTP {response.status_code} — {response.text[:300]}"
        )
    data = response.json()
    if not data.get("url"):
        raise MediaDownloadError(
            f"No 'url' field in media resolution response: {data}"
        )
    logger.info(
        "whatsapp_media_resolved",
        media_id=media_id,
        mime_type=data.get("mime_type"),
        file_size=data.get("file_size"),
    )
    return data


async def download_voice_note(
    media_id: str,
    access_token: str,
    dest_path: Path,
    max_size_bytes: int,
) -> int:
    """Resolve `media_id`, check declared file_size BEFORE downloading,
    then stream-download to `dest_path` with a mid-stream size guard.

    Checking the declared size first avoids spending bandwidth + time on an
    oversized file. The mid-stream guard catches cases where the declared
    size is missing or inaccurate.

    Returns the number of bytes written.
    """
    metadata = await _resolve_media_metadata(media_id, access_token)
    url: str = metadata["url"]

    # Pre-download size check — uses Meta's declared file_size (bytes).
    declared_size = metadata.get("file_size")
    if declared_size and int(declared_size) > max_size_bytes:
        raise MediaDownloadError(
            f"Voice note declared size {int(declared_size) / 1_048_576:.1f} MB "
            f"exceeds limit {max_size_bytes / 1_048_576:.1f} MB — skipping download"
        )

    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT_SECONDS) as client:
        async with client.stream(
            "GET", url, headers={"Authorization": f"Bearer {access_token}"}
        ) as response:
            if response.status_code != 200:
                raise MediaDownloadError(
                    f"Voice note download failed: HTTP {response.status_code}"
                )
            total = 0
            with dest_path.open("wb") as fh:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    total += len(chunk)
                    if total > max_size_bytes:
                        raise MediaDownloadError(
                            f"Voice note exceeds size limit "
                            f"({total / 1_048_576:.1f} MB > "
                            f"{max_size_bytes / 1_048_576:.1f} MB)"
                        )
                    fh.write(chunk)

    logger.info(
        "whatsapp_voice_downloaded",
        media_id=media_id,
        bytes=total,
        dest=str(dest_path),
    )
    return total


async def upload_voice_reply(
    ogg_path: Path,
    access_token: str,
    phone_number_id: str,
) -> str:
    """Upload an OGG/OPUS audio file to Meta's servers.

    Returns the `media_id` that can be passed to send_audio_message.
    The file must already be in WhatsApp-compatible OGG/OPUS format
    (use audio_converter.to_ogg_opus_mono first).
    """
    async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT_SECONDS) as client:
        with ogg_path.open("rb") as fh:
            response = await client.post(
                f"{GRAPH_API_BASE}/{phone_number_id}/media",
                headers={"Authorization": f"Bearer {access_token}"},
                # Exact MIME type required for WhatsApp to render as a voice
                # bubble (with waveform) rather than a generic file attachment.
                data={"messaging_product": "whatsapp", "type": "audio/ogg; codecs=opus"},
                files={"file": ("voice_reply.ogg", fh, "audio/ogg; codecs=opus")},
            )

    if response.status_code != 200:
        raise MediaUploadError(
            f"Media upload failed: HTTP {response.status_code} — {response.text[:300]}"
        )
    data = response.json()
    media_id: str | None = data.get("id")
    if not media_id:
        raise MediaUploadError(f"No 'id' in media upload response: {data}")

    logger.info("whatsapp_voice_uploaded", media_id=media_id, bytes=ogg_path.stat().st_size)
    return media_id


async def send_audio_message(
    org_id: uuid.UUID, phone_number: str, media_id: str
) -> str | None:
    """Send an already-uploaded audio file as a WhatsApp audio message.

    Returns the Meta message id (wamid) on success, None on failure.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "audio",
        "audio": {"id": media_id},
    }
    return await _post_message(org_id, payload)
