'use strict';
// Extract the production method and its real fs adapter; never mock writes.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const os = require('node:os');

function extract(source, signature) {
  const start = source.indexOf(signature);
  assert.ok(start >= 0 && source.indexOf(signature, start + 1) < 0, `unique ${signature}`);
  let depth = 0;
  let quote = null;
  let escape = false;
  for (let i = source.indexOf('{', start); i < source.length; ++i) {
    const c = source[i];
    if (quote) {
      if (escape) escape = false;
      else if (c === '\\') escape = true;
      else if (c === quote) quote = null;
    } else if (c === '"' || c === "'" || c === '`') quote = c;
    else if (c === '{') depth++;
    else if (c === '}' && --depth === 0) return source.slice(start, i + 1);
  }
  throw new Error(`unterminated ${signature}`);
}

async function main() {
  const bytes = fs.readFileSync(process.argv[2]);
  const source = bytes.toString('utf8');
  const adapter = extract(source, 'get write(){return(i,n,e,t,r)=>new Promise(');
  const methods = [
    extract(source, 'normalizePos(e,t){'),
    extract(source, 'updatePos(e,t,r){'),
    extract(source, 'async doWrite(e,t,r,o,s){'),
  ];
  const Adapter = new Function('Ee', `return class { ${adapter} }`)(fs);
  const Se = new Adapter();
  const Provider = new Function('Se', `return class {
    constructor(){this.mapHandleToPos=new Map();this.writeHandles=new Map();this.errors=[]}
    async toFileSystemProviderWriteError(handle,error){this.errors.push(error.code);return error}
    ${methods.join('\n')}
  }`)(Se);
  const dir = fs.mkdtempSync(path.join(process.argv[3] || os.tmpdir(), 'loopy-code-write-'));
  const file = path.join(dir, 'public-fixture');
  const results = [];
  const descriptors = new Set();
  const open = (flags) => { const fd = fs.openSync(file, flags); descriptors.add(fd); return fd; };
  const close = (fd) => { fs.closeSync(fd); descriptors.delete(fd); };
  const make = (fd, position = 0) => {
    const provider = new Provider();
    provider.mapHandleToPos.set(fd, position);
    provider.writeHandles.set(fd, 'public-fixture');
    return provider;
  };
  const run = async (name, body) => {
    try { await body(); results.push({name, phase: 'PASS'}); }
    catch (error) { results.push({name, phase: 'FAIL', code: error.code || null, message: error.message}); }
  };
  try {
    await run('empty Uint8Array creates an empty configuration', async () => {
      const fd = open('w'); const provider = make(fd); const buffer = new Uint8Array(0);
      assert.equal(await provider.doWrite(fd, 0, buffer, 0, 0), 0);
      assert.equal(buffer.byteLength, 0);
      assert.equal(fs.statSync(file).size, 0);
      assert.equal(provider.mapHandleToPos.get(fd), 0);
      close(fd);
    });
    await run('empty Buffer keeps truncation and implicit position', async () => {
      fs.writeFileSync(file, 'prior configuration');
      const fd = open('w'); const provider = make(fd);
      assert.equal(await provider.doWrite(fd, 0, Buffer.alloc(0), 0, 0), 0);
      assert.equal(fs.readFileSync(file).length, 0);
      assert.equal(provider.mapHandleToPos.get(fd), 0); close(fd);
    });
    await run('positive writes preserve offsets and explicit position', async () => {
      fs.writeFileSync(file, '012345');
      const fd = open('r+'); const provider = make(fd);
      assert.equal(await provider.doWrite(fd, 1, Buffer.from('__abc__'), 2, 3), 3);
      assert.equal(fs.readFileSync(file, 'utf8'), '0abc45');
      assert.equal(provider.mapHandleToPos.get(fd), 0); close(fd);
    });
    await run('sequential writes preserve descriptor and tracked positions', async () => {
      const fd = open('w'); const provider = make(fd);
      assert.equal(await provider.doWrite(fd, 0, Buffer.from('AB'), 0, 2), 2);
      assert.equal(await provider.doWrite(fd, 2, new Uint8Array([67, 68]), 0, 2), 2);
      assert.equal(fs.readFileSync(file, 'utf8'), 'ABCD');
      assert.equal(provider.mapHandleToPos.get(fd), 4); close(fd);
    });
    await run('zero count with a nonempty backing buffer stays zero', async () => {
      fs.writeFileSync(file, 'keep');
      const fd = open('r+'); const provider = make(fd);
      assert.equal(await provider.doWrite(fd, 0, new Uint8Array([65]), 0, 0), 0);
      assert.equal(fs.readFileSync(file, 'utf8'), 'keep'); close(fd);
    });
    await run('empty writes still report invalid descriptors', async () => {
      const provider = make(123456);
      await assert.rejects(provider.doWrite(123456, 0, new Uint8Array(0), 0, 0), {code: 'EBADF'});
      assert.deepEqual(provider.errors, ['EBADF']);
      assert.equal(provider.mapHandleToPos.has(123456), false);
    });
    await run('empty writes still report read-only descriptors', async () => {
      fs.writeFileSync(file, 'keep');
      const fd = open('r'); const provider = make(fd);
      await assert.rejects(provider.doWrite(fd, 0, new Uint8Array(0), 0, 0), {code: 'EBADF'});
      assert.deepEqual(provider.errors, ['EBADF']);
      assert.equal(provider.mapHandleToPos.has(fd), false);
      assert.equal(fs.readFileSync(file, 'utf8'), 'keep'); close(fd);
    });
    await run('invalid offsets are not hidden by the empty-write guard', async () => {
      const fd = open('w'); const provider = make(fd);
      await assert.rejects(provider.doWrite(fd, 0, new Uint8Array(0), 1, 0), {code: 'ERR_OUT_OF_RANGE'});
      assert.equal(provider.mapHandleToPos.has(fd), false); close(fd);
    });
    await run('empty writes retain explicit position accounting', async () => {
      fs.writeFileSync(file, 'keep');
      const fd = open('r+'); const provider = make(fd, 2);
      assert.equal(await provider.doWrite(fd, 1, new Uint8Array(0), 0, 0), 0);
      assert.equal(provider.mapHandleToPos.get(fd), 2);
      assert.equal(fs.readFileSync(file, 'utf8'), 'keep'); close(fd);
    });
  } finally {
    for (const fd of descriptors) fs.closeSync(fd);
    if (fs.existsSync(file)) fs.unlinkSync(file);
    fs.rmdirSync(dir);
  }
  const phase = results.every(row => row.phase === 'PASS') ? 'PASS' : 'FAIL';
  console.log(JSON.stringify({schema: 1, phase, sourceSha256: crypto.createHash('sha256').update(bytes).digest('hex'),
    node: process.version, electron: process.versions.electron || null, writesMocked: false,
    cases: results.length, results}));
  process.exitCode = phase === 'PASS' ? 0 : 1;
}
main().catch(error => { console.error(error.stack); process.exitCode = 1; });
