import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../termux/browser-performance/prefer-h264.js',import.meta.url),'utf8');
function context(hostname){class Media{};Media.prototype.canPlayType=function(){assert.ok(this instanceof Media);return 'probably'};const value={location:{hostname},HTMLMediaElement:Media,MediaSource:{isTypeSupported(){return true}},Reflect};vm.createContext(value);vm.runInContext(source,value);return value}
const c=context('www.youtube.com');
for(const mime of ['video/mp4; codecs="av01.0.08M.08"','video/webm; codecs="vp9"','video/webm; codecs="vp09.00.41.08"']){
 assert.equal(c.MediaSource.isTypeSupported(mime),false);assert.equal(new c.HTMLMediaElement().canPlayType(mime),'');
}
for(const mime of ['video/mp4; codecs="avc1.640028"','audio/webm; codecs="opus"','video/mp4; codecs="hvc1"','',null]){
 assert.equal(c.MediaSource.isTypeSupported(mime),true);assert.equal(new c.HTMLMediaElement().canPlayType(mime),'probably');
}
const unrelated=context('www.notion.so');assert.equal(unrelated.MediaSource.isTypeSupported('video/mp4; codecs="av01.0.08M.08"'),true);
console.log('PASS YouTube codec selection, H264/audio/other codecs retained, unrelated sites untouched');
