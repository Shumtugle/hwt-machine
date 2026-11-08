"""Read and write the watch face container (layout format version 2).

A package is a zip with a short XML manifest, a few preview pictures and one binary.
The binary is:

    u16 version (2) | u16 layout length | u32 table length | u32 blob length | u32 zero
    layout   protobuf message: groups of elements, see the format notes
    table    one (u32 offset, u32 size) pair per image, offsets relative to the blob
    blob     8-byte marker, then the encoded images back to back

Images are referenced from the layout by their 1-based index written as three digits.
"""
import io
import struct
import zipfile

from PIL import Image

INNER_NAME = 'com.huawei.watchface'
IMG_MAGIC = b'\x45\x23\x88\x88'
RUN_MAGIC = b'\x89\x67\x45\x23'
BLOB_MARK = b'\x55\x55\x55\x55\x01\x00\x00\x01'
RUN_MIN = 4  # runs this long or longer are stored as (marker, colour, count)


# ---------------------------------------------------------------- images

def encode_image(img):
    """PIL image -> bytes: BGRA pixels, runs of RUN_MIN or more collapsed."""
    img = img.convert('RGBA')
    w, h = img.size
    px = img.tobytes('raw', 'BGRA')
    out = bytearray(IMG_MAGIC + struct.pack('<HH', w, h))
    n = w * h
    i = 0
    while i < n:
        c = px[4 * i:4 * i + 4]
        j = i + 1
        while j < n and px[4 * j:4 * j + 4] == c:
            j += 1
        k = j - i
        if k >= RUN_MIN:
            out += RUN_MAGIC + c + struct.pack('<I', k)
        else:
            out += c * k
        i = j
    return bytes(out)


def decode_image(blob):
    """bytes -> PIL RGBA image."""
    if blob[:4] != IMG_MAGIC:
        raise ValueError('not an image')
    w, h = struct.unpack('<HH', blob[4:8])
    px = bytearray()
    i = 8
    while i < len(blob):
        if blob[i:i + 4] == RUN_MAGIC:
            px += blob[i + 4:i + 8] * struct.unpack('<I', blob[i + 8:i + 12])[0]
            i += 12
        else:
            px += blob[i:i + 4]
            i += 4
    if len(px) != w * h * 4:
        raise ValueError('pixel count mismatch')
    return Image.frombytes('RGBA', (w, h), bytes(px), 'raw', 'BGRA')


# ---------------------------------------------------------------- protobuf

def _varint(v):
    if v < 0:
        v += 1 << 64
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def pb_encode(fields):
    """[(number, value)] -> bytes; value is int, str, bytes or a nested list."""
    out = bytearray()
    for num, val in fields:
        if isinstance(val, bool):
            val = int(val)
        if isinstance(val, int):
            out += _varint(num << 3) + _varint(val)
        else:
            if isinstance(val, list):
                body = pb_encode(val)
            elif isinstance(val, str):
                body = val.encode('utf-8')
            else:
                body = bytes(val)
            out += _varint((num << 3) | 2) + _varint(len(body)) + body
    return bytes(out)


def _read_varint(b, i):
    r = s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return r, i


def pb_decode(b):
    """bytes -> [(number, value)]. The schema is not stored, so a length-delimited
    field is taken as a nested message when it parses as one and is not plain text."""
    out = []
    i = 0
    while i < len(b):
        key, i = _read_varint(b, i)
        f, t = key >> 3, key & 7
        if t == 0:
            v, i = _read_varint(b, i)
            if v >= 1 << 63:
                v -= 1 << 64
            out.append((f, v))
        elif t == 2:
            n, i = _read_varint(b, i)
            sub = bytes(b[i:i + n])
            i += n
            val = sub
            if n and not all(32 <= c < 127 for c in sub):
                try:
                    val = pb_decode(sub)
                except (ValueError, IndexError):
                    val = sub
            if isinstance(val, bytes):
                try:
                    val = sub.decode('utf-8')
                except UnicodeDecodeError:
                    pass
            out.append((f, val))
        elif t == 5:
            out.append((f, struct.unpack('<I', b[i:i + 4])[0]))
            i += 4
        elif t == 1:
            out.append((f, struct.unpack('<Q', b[i:i + 8])[0]))
            i += 8
        else:
            raise ValueError('wire type %d' % t)
    if i != len(b):
        raise ValueError('overrun')
    return out


# ---------------------------------------------------------------- binary

def pack(layout, images):
    """layout bytes + PIL images -> binary."""
    blobs = [encode_image(im) for im in images]
    table = bytearray()
    off = len(BLOB_MARK)
    for b in blobs:
        table += struct.pack('<II', off, len(b))
        off += len(b)
    blob = BLOB_MARK + b''.join(blobs)
    if len(layout) > 0xFFFF:
        raise ValueError('layout too large')
    head = struct.pack('<HHIII', 2, len(layout), len(table), len(blob), 0)
    return head + layout + bytes(table) + blob


def unpack(binary, strict=False):
    """binary -> (layout tree, [PIL images])."""
    ver, plen, tlen, dlen, _ = struct.unpack('<HHIII', binary[:16])
    if ver != 2:
        raise ValueError('unsupported version %d' % ver)
    layout = binary[16:16 + plen]
    t = 16 + plen
    base = t + tlen
    if strict and base + dlen != len(binary):
        raise ValueError('length fields disagree with file size')
    images = []
    for i in range(tlen // 8):
        off, size = struct.unpack('<II', binary[t + 8 * i:t + 8 * i + 8])
        blob = binary[base + off:base + off + size]
        if blob[:4] != IMG_MAGIC and not strict:
            images.append(None)  # another image encoding, not supported here
            continue
        images.append(decode_image(blob))
    return pb_decode(layout), images


# ---------------------------------------------------------------- package

MANIFEST = '''<?xml version="1.0" encoding="UTF-8"?>
<HwTheme>
  <title>{title}</title>
  <title-cn>{title}</title-cn>
  <author>{author}</author>
  <designer>{author}</designer>
  <screen>{screen}</screen>
  <version>{version}</version>
  <font>Default</font>
  <font-cn>Default</font-cn>
  <briefinfo>{{}}</briefinfo>
</HwTheme>
'''


def write_package(path, binary, title, author, screen, version, previews):
    """previews: name -> JPEG bytes, usually cover, icon_small and aod."""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('description.xml', MANIFEST.format(
            title=title, author=author, screen=screen, version=version))
        z.writestr(INNER_NAME, binary)
        for name, data in previews.items():
            z.writestr('preview/' + name, data)


def read_package(path_or_bytes):
    """-> (manifest text, binary, {preview name: bytes})."""
    src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        manifest = z.read('description.xml').decode('utf-8', 'replace') if 'description.xml' in names else ''
        binary = z.read(INNER_NAME)
        if binary[:2] == b'PK':
            # some packages nest a second archive that holds the binary
            with zipfile.ZipFile(io.BytesIO(binary)) as inner:
                binary = next(inner.read(n) for n in inner.namelist() if n.endswith('.bin'))
        previews = {n.split('/', 1)[1]: z.read(n) for n in names if n.startswith('preview/') and not n.endswith('/')}
    return manifest, binary, previews
