// Reads a watch face package in the browser and draws it the way the watch would.
// Mirrors the Python simulator: same layout reading, same element kinds.

const HWT = (() => {
  const IMG_MAGIC = [0x45, 0x23, 0x88, 0x88];
  const RUN_MAGIC = [0x89, 0x67, 0x45, 0x23];
  const BODY = { 0: 3, 1: 4, 2: 5, 3: 6, 5: 8, 6: 9, 7: 10, 10: 11 };

  // ---------------------------------------------------------------- zip

  async function inflateRaw(bytes) {
    const ds = new DecompressionStream('deflate-raw');
    const out = new Blob([bytes]).stream().pipeThrough(ds);
    return new Uint8Array(await new Response(out).arrayBuffer());
  }

  async function unzip(buf) {
    const u8 = new Uint8Array(buf);
    const dv = new DataView(buf);
    let eocd = -1;
    for (let i = u8.length - 22; i >= Math.max(0, u8.length - 65557); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('not a zip archive');
    const count = dv.getUint16(eocd + 10, true);
    let p = dv.getUint32(eocd + 16, true);
    const files = {};
    const dec = new TextDecoder();
    for (let n = 0; n < count; n++) {
      const method = dv.getUint16(p + 10, true);
      const csize = dv.getUint32(p + 20, true);
      const nlen = dv.getUint16(p + 28, true), xlen = dv.getUint16(p + 30, true), clen = dv.getUint16(p + 32, true);
      const local = dv.getUint32(p + 42, true);
      const name = dec.decode(u8.subarray(p + 46, p + 46 + nlen));
      const lnlen = dv.getUint16(local + 26, true), lxlen = dv.getUint16(local + 28, true);
      const start = local + 30 + lnlen + lxlen;
      const raw = u8.subarray(start, start + csize);
      files[name] = method === 0 ? raw.slice() : method === 8 ? await inflateRaw(raw) : null;
      p += 46 + nlen + xlen + clen;
    }
    return files;
  }

  // ---------------------------------------------------------------- protobuf

  function readVarint(b, i) {
    let r = 0n, s = 0n;
    for (;;) {
      if (i >= b.length || s > 63n) throw new Error('truncated varint');
      const c = b[i++];
      r |= BigInt(c & 0x7f) << s;
      s += 7n;
      if (c < 0x80) return [r, i];
    }
  }

  function toNumber(v) {
    if (v >= (1n << 63n)) v -= 1n << 64n;
    else if (v >= (1n << 31n) && v < (1n << 32n)) v -= 1n << 32n;
    return Number(v);
  }

  function printable(b) {
    for (const c of b) if (c < 32 || c > 126) return false;
    return true;
  }

  function decode(b) {
    const out = [];
    let i = 0;
    while (i < b.length) {
      let key;
      [key, i] = readVarint(b, i);
      const f = Number(key >> 3n), t = Number(key & 7n);
      if (t === 0) {
        let v;
        [v, i] = readVarint(b, i);
        out.push([f, toNumber(v)]);
      } else if (t === 2) {
        let n;
        [n, i] = readVarint(b, i);
        n = Number(n);
        const sub = b.subarray(i, i + n);
        i += n;
        let val = null;
        if (n && !printable(sub)) { try { val = decode(sub); } catch (e) { val = null; } }
        if (val === null) val = new TextDecoder().decode(sub);
        out.push([f, val]);
      } else if (t === 5) { out.push([f, new DataView(b.buffer, b.byteOffset + i, 4).getUint32(0, true)]); i += 4; }
      else if (t === 1) { i += 8; }
      else throw new Error('wire type ' + t);
    }
    if (i !== b.length) throw new Error('overrun');
    return out;
  }

  const get = (node, f, d) => { for (const [k, v] of node) if (k === f) return v; return d; };
  const all = (node, f) => node.filter(([k]) => k === f).map(([, v]) => v);

  // ---------------------------------------------------------------- images

  function same(b, i, m) { return b[i] === m[0] && b[i + 1] === m[1] && b[i + 2] === m[2] && b[i + 3] === m[3]; }

  function decodeImage(b) {
    if (!same(b, 0, IMG_MAGIC)) return null;
    const w = b[4] | (b[5] << 8), h = b[6] | (b[7] << 8);
    const px = new Uint8ClampedArray(w * h * 4);
    let o = 0, i = 8;
    const put = (j) => { px[o] = b[j + 2]; px[o + 1] = b[j + 1]; px[o + 2] = b[j]; px[o + 3] = b[j + 3]; o += 4; };
    while (i < b.length && o < px.length) {
      if (same(b, i, RUN_MAGIC)) {
        const n = b[i + 8] | (b[i + 9] << 8) | (b[i + 10] << 16) | (b[i + 11] << 24);
        for (let k = 0; k < n && o < px.length; k++) put(i + 4);
        i += 12;
      } else { put(i); i += 4; }
    }
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    c.getContext('2d').putImageData(new ImageData(px, w, h), 0, 0);
    return c;
  }

  // ---------------------------------------------------------------- package

  async function load(buf) {
    const files = await unzip(buf);
    let bin = files['com.huawei.watchface'];
    if (!bin) throw new Error('no watch face inside');
    if (bin[0] === 0x50 && bin[1] === 0x4b) {
      const inner = await unzip(bin.buffer.slice(bin.byteOffset, bin.byteOffset + bin.length));
      bin = Object.entries(inner).find(([n]) => n.endsWith('.bin'))[1];
    }
    const dv = new DataView(bin.buffer, bin.byteOffset, bin.length);
    const ver = dv.getUint16(0, true), plen = dv.getUint16(2, true), tlen = dv.getUint32(4, true);
    if (ver !== 2) throw new Error('unsupported version ' + ver);
    const tree = decode(bin.subarray(16, 16 + plen));
    const t = 16 + plen, base = t + tlen;
    const table = [];
    for (let i = 0; i < tlen / 8; i++) table.push([dv.getUint32(t + 8 * i, true), dv.getUint32(t + 8 * i + 4, true)]);
    const cache = new Map();
    const image = (ref) => {
      const idx = parseInt(ref, 10) - 1;
      if (!cache.has(idx)) {
        const [off, size] = table[idx] || [0, 0];
        cache.set(idx, size ? decodeImage(bin.subarray(base + off, base + off + size)) : null);
      }
      return cache.get(idx);
    };
    const manifest = files['description.xml'] ? new TextDecoder().decode(files['description.xml']) : '';
    const title = (manifest.match(/<title>([^<]*)/) || [, ''])[1];
    return { tree, image, title, images: table.length };
  }

  // ---------------------------------------------------------------- drawing

  function sampleData(now, s) {
    const d = {
      59: Math.floor(now.getHours() / 10), 60: now.getHours() % 10,
      61: Math.floor(now.getMinutes() / 10), 62: now.getMinutes() % 10,
      63: Math.floor(now.getSeconds() / 10), 64: now.getSeconds() % 10,
      51: now.getMonth() + 1, 52: ((now.getDay() + 6) % 7) + 1, 17: now.getDate(),
      70: Math.floor(now.getDate() / 10), 71: now.getDate() % 10,
      12: now.getHours(), 13: now.getMinutes(), 14: now.getSeconds(),
      53: s.weather, 54: Math.min(10, Math.floor(s.battery / 10)), 72: 0,
      0: s.steps, 1: 328, 2: s.heart, 4: s.temp, 9: s.battery,
    };
    d.time = now;
    return d;
  }

  // pick: which choice to show in editable zones, by position in the zone's list;
  // undefined shows each zone's default, as the watch does before anything is chosen.
  function render(ctx, face, data, aod, pick) {
    const flag = aod ? 1 : 0;
    let origin = [0, 0];
    const off = (body, field) => {
      const o = get(body, field);
      return Array.isArray(o) ? [origin[0] + get(o, 1, 0), origin[1] + get(o, 2, 0)] : [0, 0];
    };
    const skipped = new Set();
    ctx.save();
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    const draw = (el) => {
      const kind = get(el, 2);
      const body = get(el, BODY[kind]);
      if (!Array.isArray(body)) { skipped.add(kind); return; }
      if (kind === 1) {
        if (get(body, 5, 0) !== flag) return;
        const p = get(body, 2, []), im = face.image(get(body, 1)), [ox, oy] = off(body, 4);
        if (im) ctx.drawImage(im, get(p, 1, 0) + ox, get(p, 2, 0) + oy);
      } else if (kind === 2) {
        if (get(body, 6, 0) !== flag) return;
        const refs = all(body, 1).filter((r) => typeof r === 'string');
        const idx = data[get(body, 3)];
        if (idx === undefined || idx < 0 || idx >= refs.length) return;
        const p = get(body, 2, []), im = face.image(refs[idx]), [ox, oy] = off(body, 5);
        if (im) ctx.drawImage(im, get(p, 1, 0) + ox, get(p, 2, 0) + oy);
      } else if (kind === 3) {
        if (get(body, 13, 0) !== flag) return;
        const refs = all(body, 1).filter((r) => typeof r === 'string');
        const v = data[get(body, 5)];
        if (v === undefined) return;
        const parts = String(Math.abs(v)).split('').map((c) => face.image(refs[+c])).filter(Boolean);
        const minus = get(body, 6, '');
        if (v < 0 && minus && face.image(minus)) parts.unshift(face.image(minus));
        const width = parts.reduce((a, p) => a + p.width, 0);
        const p = get(body, 3, []), [ox, oy] = off(body, 10);
        let x = get(p, 1, 0) + ox;
        const y = get(p, 2, 0) + oy, align = get(body, 4, 0);
        if (align === 2) x -= width; else if (align === 1) x -= Math.floor(width / 2);
        for (const part of parts) { ctx.drawImage(part, x, y); x += part.width; }
      } else if (kind === 5) {
        if (get(body, 9, 0) !== flag) return;
        const t = data.time;
        const angle = { 150: ((t.getHours() % 12) + t.getMinutes() / 60) * 30,
                        153: (t.getMinutes() + t.getSeconds() / 60) * 6,
                        154: t.getSeconds() * 6 }[get(body, 6)];
        if (angle === undefined) return;
        const r = get(body, 2, []), pv = get(body, 3, []), im = face.image(get(body, 1));
        if (!im) return;
        ctx.save();
        ctx.translate(get(r, 1, 0) + get(r, 3, 0) / 2, get(r, 2, 0) + get(r, 4, 0) / 2);
        ctx.rotate(angle * Math.PI / 180);
        ctx.drawImage(im, -get(pv, 1, 0), -get(pv, 2, 0));
        ctx.restore();
      } else if (kind === 0 || kind === 10) {
        // system-font text: the watch's own font is not available here, so this is an approximation
        const flagField = kind === 0 ? 7 : 9;
        if ((get(body, flagField, 0) || 0) !== flag) return;
        const r = get(body, 1, []), c = get(body, 2, []);
        const v = data[get(body, 5)];
        if (v === undefined || !r.length) return;
        const unit = kind === 10 ? ({ 9: '%', 4: '°' }[get(body, 6)] || '') : '';
        const x = get(r, 1, 0), y = get(r, 2, 0), w = get(r, 3, 0), h = get(r, 4, 0);
        ctx.save();
        ctx.fillStyle = 'rgba(' + get(c, 1, 255) + ',' + get(c, 2, 255) + ',' + get(c, 3, 255) + ',' + (get(c, 4, 255) / 255) + ')';
        ctx.font = '500 ' + Math.round(h * 0.86) + 'px system-ui, sans-serif';
        ctx.textBaseline = 'middle';
        const align = get(body, 4, 0);
        ctx.textAlign = align === 1 ? 'center' : align === 2 ? 'right' : 'left';
        ctx.fillText(String(v) + unit, align === 1 ? x + w / 2 : align === 2 ? x + w : x, y + h / 2);
        ctx.restore();
      } else skipped.add(kind);
    };
    for (const [k, group] of face.tree) {
      if (k !== 1 || !Array.isArray(group)) continue;
      const slots = new Map(group.filter(([f, v]) => f === 7 && Array.isArray(v)).map(([, v]) => [get(v, 1, 0), v]));
      for (const [f, item] of group) {
        if (f === 5 && Array.isArray(item)) draw(item);
        else if (f === 8 && Array.isArray(item)) {
          if (get(item, 2) === 1) {
            const list = get(item, 3, '');
            const ids = typeof list === 'string' ? [...list].map((c) => c.charCodeAt(0)) :
              Array.isArray(list) ? list.flat() : [];
            let chosen = get(item, 4, 0);
            if (pick !== undefined && ids.length) chosen = ids[Math.min(pick, ids.length - 1)];
            const slot = slots.get(chosen), r = get(item, 5, []);
            if (slot) {
              origin = [get(r, 1, 0), get(r, 2, 0)];
              for (const [g, sub] of slot) if (g === 2 && Array.isArray(sub)) draw(sub);
              origin = [0, 0];
            }
          } else for (const [g, sub] of item) if (g === 6 && Array.isArray(sub)) draw(sub);
        }
      }
    }
    ctx.restore();
    return [...skipped];
  }

  return { load, render, sampleData };
})();
