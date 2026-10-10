import asyncio
import shutil
import tempfile
from pathlib import Path


def available(ebook_convert: str) -> bool:
    return shutil.which(ebook_convert) is not None


async def convert(data: bytes, src_ext: str, dst_ext: str, ebook_convert: str) -> bytes:
    """Конвертация через calibre (ebook-convert)."""
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d, f"in.{src_ext}"), Path(d, f"out.{dst_ext}")
        src.write_bytes(data)
        proc = await asyncio.create_subprocess_exec(
            ebook_convert, str(src), str(dst),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("конвертация заняла слишком много времени")
        if proc.returncode != 0 or not dst.exists():
            raise RuntimeError(err.decode("utf-8", "replace")[-300:] or "ebook-convert failed")
        return dst.read_bytes()
