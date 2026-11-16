"""Private file storage for confidential investor documents (CR-C6).

Files are written under ``settings.PRIVATE_STORAGE_DIR`` with random names. That directory is
not served by Next.js, Caddy or FastAPI static routes; the only way out is an authenticated
download endpoint that first checks ownership in the database.
"""

import asyncio
import hashlib
import logging
import re
import secrets
import struct
from pathlib import Path

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Accepted upload types, identified by leading bytes rather than by the client-declared type.
_SIGNATURES: dict[str, bytes] = {"application/pdf": b"%PDF-"}
_CHUNK = 64 * 1024

# PDF features that run code or carry other files. Financial reports and investment documents do
# not need them, and they are the usual vehicles for malicious PDFs, so such files are refused.
_ACTIVE_PDF_NAMES = {b"JavaScript", b"JS", b"Launch", b"EmbeddedFile", b"EmbeddedFiles", b"RichMedia", b"SubmitForm", b"ImportData"}
_PDF_NAME = re.compile(rb"/((?:[A-Za-z0-9._+\-]|#[0-9A-Fa-f]{2})+)")
_HEX_ESCAPE = re.compile(rb"#([0-9A-Fa-f]{2})")


def _decode_name(raw: bytes) -> bytes:
    """PDF names may hex-escape characters (/J#61vaScript == /JavaScript)."""
    return _HEX_ESCAPE.sub(lambda m: bytes([int(m.group(1), 16)]), raw)


def inspect_pdf(path: Path) -> str | None:
    """Structural checks on a stored PDF. Returns a reason to reject it, or None.

    This is a filter, not a malware scanner: names inside compressed object streams are not
    visible to it. Enable DOCUMENT_SCAN_MODE=clamav for signature-based scanning as well.
    """
    data = path.read_bytes()
    if b"%%EOF" not in data[-2048:]:
        return "The PDF appears to be incomplete or damaged"
    for match in _PDF_NAME.finditer(data):
        if _decode_name(match.group(1)) in _ACTIVE_PDF_NAMES:
            return "PDFs containing scripts, launch actions, embedded files or form submission are not accepted"
    return None


class ScannerUnavailable(RuntimeError):
    pass


async def clamav_scan(path: Path) -> str | None:
    """Streams the file to clamd (INSTREAM). Returns the signature name if infected, else None.

    Raises ScannerUnavailable on any connection or protocol problem so callers can fail closed.
    """
    async def _scan() -> str | None:
        reader, writer = await asyncio.open_connection(settings.CLAMAV_HOST, settings.CLAMAV_PORT)
        try:
            writer.write(b"zINSTREAM\0")
            with path.open("rb") as handle:
                while chunk := handle.read(_CHUNK):
                    writer.write(struct.pack(">I", len(chunk)) + chunk)
                    await writer.drain()
            writer.write(struct.pack(">I", 0))
            await writer.drain()
            reply = (await reader.readuntil(b"\0")).rstrip(b"\0").decode("utf-8", "replace").strip()
        finally:
            writer.close()
        if reply.endswith("OK"):
            return None
        if reply.endswith("FOUND"):
            return reply.split(":", 1)[-1].removesuffix("FOUND").strip() or "malware"
        raise ScannerUnavailable(f"Unexpected scanner reply ({reply[:40]!r})")

    try:
        return await asyncio.wait_for(_scan(), timeout=settings.CLAMAV_TIMEOUT_SECONDS)
    except ScannerUnavailable:
        raise
    except (TimeoutError, OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
        raise ScannerUnavailable(type(exc).__name__) from exc


async def _screen_document(path: Path) -> None:
    reason = await asyncio.to_thread(inspect_pdf, path)
    if reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=reason)
    if (settings.DOCUMENT_SCAN_MODE or "off").strip().lower() == "clamav":
        try:
            signature = await clamav_scan(path)
        except ScannerUnavailable as exc:
            logger.error("Document scanner unavailable (%s); upload refused", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document scanning is unavailable, so the document was not stored. Please try again later.",
            ) from exc
        if signature:
            logger.warning("Uploaded document rejected by malware scan (%s)", signature)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The document was rejected by the malware scan and was not stored.",
            )


def storage_root() -> Path:
    root = Path(settings.PRIVATE_STORAGE_DIR).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def resolve_storage_path(storage_key: str) -> Path:
    """Maps a stored key to its path, refusing anything that would escape the storage root."""
    root = storage_root()
    path = (root / storage_key).resolve()
    if path.parent != root or not storage_key or "/" in storage_key or "\\" in storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return path


async def store_upload(request: Request) -> tuple[str, str, int, str]:
    """Streams the request body to private storage.

    Returns (storage_key, content_type, size_bytes, sha256). Enforces the size limit while
    streaming (never trusting Content-Length), validates the file signature, refuses PDFs with
    active content and, when DOCUMENT_SCAN_MODE=clamav, scans with ClamAV (fail closed). A file
    that fails any check is deleted before the error is returned.
    """
    limit = settings.MAX_DOCUMENT_BYTES
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail="Document exceeds the size limit")

    storage_key = f"{secrets.token_hex(24)}.bin"
    path = storage_root() / storage_key
    digest = hashlib.sha256()
    size = 0
    head = b""
    try:
        with path.open("xb") as handle:
            path.chmod(0o600)
            async for chunk in request.stream():
                if not chunk:
                    continue
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status_code=413, detail="Document exceeds the size limit"
                    )
                if len(head) < 16:
                    head += chunk[: 16 - len(head)]
                digest.update(chunk)
                handle.write(chunk)
        if size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded document is empty")
        content_type = next((ct for ct, sig in _SIGNATURES.items() if head.startswith(sig)), None)
        if content_type is None:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only PDF documents are accepted",
            )
        await _screen_document(path)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return storage_key, content_type, size, digest.hexdigest()


def remove_stored_file(storage_key: str) -> None:
    """Best-effort cleanup used when the database insert that should own the file fails."""
    try:
        resolve_storage_path(storage_key).unlink(missing_ok=True)
    except HTTPException:
        pass
