import { watch } from 'node:fs';
import { join } from 'node:path';
const root = import.meta.dir;
const clients = new Set<any>();
const transpiler = new Bun.Transpiler({ loader: 'ts' });
const server = Bun.serve({
  hostname: '127.0.0.1', port: 4173,
  async fetch(req, server) {
    const path = new URL(req.url).pathname;
    if (path === '/live' && server.upgrade(req)) return;
    if (path === '/health') return Response.json({ ok: true, runtime: Bun.version });
    if (path === '/message.js') return new Response(await transpiler.transform(await Bun.file(join(root,'src/message.ts')).text()), { headers: { 'Content-Type':'text/javascript', 'Cache-Control':'no-store' } });
    if (path === '/video.mp4') return new Response(Bun.file(join(root,'video.mp4')));
    if (path === '/') return new Response(Bun.file(join(root,'index.html')), {headers:{'Cache-Control':'no-store'}});
    return new Response('Not found', {status:404});
  },
  websocket: {open(ws){clients.add(ws)}, close(ws){clients.delete(ws)}, message(){}},
});
let timer: Timer;
watch(join(root,'src'), () => {
  clearTimeout(timer);
  timer = setTimeout(() => { for(const ws of clients) ws.send('refresh'); }, 50);
});
console.log(`Tablet Dev Lab http://${server.hostname}:${server.port}`);
