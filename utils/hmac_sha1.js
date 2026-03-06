// Pure JS HMAC-SHA1 — used for Aliyun OSS request signing

function rotl(v, n) {
  return ((v << n) | (v >>> (32 - n))) >>> 0
}

function sha1(bytes) {
  const data = bytes.slice()
  const origLen = data.length * 8
  data.push(0x80)
  while ((data.length % 64) !== 56) data.push(0)
  data.push(0, 0, 0, 0,
    (origLen >>> 24) & 0xff, (origLen >>> 16) & 0xff,
    (origLen >>> 8) & 0xff, origLen & 0xff)

  let h0 = 0x67452301, h1 = 0xEFCDAB89, h2 = 0x98BADCFE,
      h3 = 0x10325476, h4 = 0xC3D2E1F0

  for (let i = 0; i < data.length; i += 64) {
    const w = []
    for (let j = 0; j < 16; j++)
      w[j] = ((data[i+j*4] << 24) | (data[i+j*4+1] << 16) |
               (data[i+j*4+2] << 8) | data[i+j*4+3]) >>> 0
    for (let j = 16; j < 80; j++)
      w[j] = rotl(w[j-3] ^ w[j-8] ^ w[j-14] ^ w[j-16], 1)

    let a = h0, b = h1, c = h2, d = h3, e = h4

    for (let j = 0; j < 80; j++) {
      let f, k
      if      (j < 20) { f = ((b & c) | (~b & d)) >>> 0; k = 0x5A827999 }
      else if (j < 40) { f = (b ^ c ^ d) >>> 0;          k = 0x6ED9EBA1 }
      else if (j < 60) { f = ((b & c) | (b & d) | (c & d)) >>> 0; k = 0x8F1BBCDC }
      else             { f = (b ^ c ^ d) >>> 0;          k = 0xCA62C1D6 }
      const t = (rotl(a, 5) + f + e + k + w[j]) >>> 0
      e = d; d = c; c = rotl(b, 30); b = a; a = t
    }
    h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0
    h3 = (h3 + d) >>> 0; h4 = (h4 + e) >>> 0
  }

  const out = []
  for (const h of [h0, h1, h2, h3, h4])
    out.push((h >>> 24) & 0xff, (h >>> 16) & 0xff, (h >>> 8) & 0xff, h & 0xff)
  return out
}

function hmacSha1(keyBytes, dataBytes) {
  let k = keyBytes.length > 64 ? sha1(keyBytes) : keyBytes.slice()
  while (k.length < 64) k.push(0)
  const inner = sha1(k.map(b => b ^ 0x36).concat(dataBytes))
  return sha1(k.map(b => b ^ 0x5c).concat(inner))
}

function base64Encode(bytes) {
  const t = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  let s = ''
  for (let i = 0; i < bytes.length; i += 3) {
    const n = (bytes[i] << 16) | ((bytes[i+1] || 0) << 8) | (bytes[i+2] || 0)
    s += t[(n >> 18) & 63] + t[(n >> 12) & 63]
    s += (i + 1 < bytes.length) ? t[(n >> 6) & 63] : '='
    s += (i + 2 < bytes.length) ? t[n & 63] : '='
  }
  return s
}

function strToBytes(s) {
  const b = []
  for (let i = 0; i < s.length; i++) b.push(s.charCodeAt(i) & 0xff)
  return b
}

function hmacSha1Base64(key, data) {
  return base64Encode(hmacSha1(strToBytes(key), strToBytes(data)))
}

module.exports = { hmacSha1Base64 }
