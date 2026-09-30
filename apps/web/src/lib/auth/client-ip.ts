import "server-only";

/**
 * IP klien asli buat diteruskan ke `cti-api` (`X-Forwarded-For`).
 *
 * Kenapa perlu: web = BFF, SEMUA request ke `cti-api` keluar dari container
 * `web`, jadi tanpa ini `request.client.host` di API selalu IP `web` --
 * rate limit login (`login:{ip}`, 10/menit) jadi GLOBAL (sepuluh salah-ketik
 * dari siapa pun mengunci semua orang) dan kolom IP di audit log gak berguna.
 *
 * Topologi: klien -> nginx -> web -> api. nginx (dipercaya) NAMBAHIN IP klien
 * di ujung KANAN `X-Forwarded-For` (`$proxy_add_x_forwarded_for`); bagian
 * kirinya bisa dipalsuin klien. Makanya diambil hop ke-N dari KANAN
 * (`TRUSTED_PROXY_HOPS`, default 1 = cukup nginx), dan yang diteruskan ke API
 * cuma SATU IP itu -- uvicorn (`--proxy-headers`, allow-ips `*`) mengambil
 * entri paling kiri, jadi kalau kita kirim rantai utuh, klien bisa nentuin IP
 * yang dilihat API.
 *
 * Tanpa `X-Forwarded-For` (dev langsung ke `pnpm dev`, gak ada proxy): gak
 * ngirim apa-apa, API tetap lihat IP peer-nya seperti sebelumnya.
 */
const IP_LIKE = /^[0-9a-fA-F:.]{2,45}$/;

export function clientIpHeaders(request: Request): Record<string, string> {
  const raw = request.headers.get("x-forwarded-for");
  if (!raw) return {};

  const hops = Math.max(1, Number.parseInt(process.env.TRUSTED_PROXY_HOPS ?? "1", 10) || 1);
  const chain = raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  const ip = chain[chain.length - hops] ?? chain[0];

  // Nilai harus keliatan kayak IP -- kolom IP audit log terbatas panjangnya,
  // dan header ini datang dari luar.
  return ip && IP_LIKE.test(ip) ? { "x-forwarded-for": ip } : {};
}
