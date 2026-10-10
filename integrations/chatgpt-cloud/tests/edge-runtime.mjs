// Actual Workers runtime regression test. Outbound HTTP is mocked; no live keys.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const wranglerRequire = createRequire(require.resolve('wrangler/package.json'));
const { Miniflare } = await import(wranglerRequire.resolve('miniflare'));
const source = await readFile(new URL('../lib/connector.mjs', import.meta.url), 'utf8');

test('workerd gateway and image fetch reject redirects without following or leaking keys', async () => {
  const requests = [];
  const token = 'tac_' + 'fixture_'.repeat(6);
  const mf = new Miniflare({
    modules: [
      { type: 'ESModule', path: 'index.mjs', contents: `
        import {gateway, importImage} from './connector.mjs';
        export default {async fetch(request) {
          const testCase = new URL(request.url).pathname;
          try {
            const env = {TAC_BASE_URL:'https://gateway.example'};
            const token = ${JSON.stringify(token)};
            const result = testCase === '/image'
              ? await importImage(env, token, {download_url:'https://files.oaiusercontent.com/image', filename:'post.png'})
              : await gateway(env, token, 'GET', testCase === '/redirect' ? '/redirect' : '/v1/system');
            return Response.json({ok:true,result});
          } catch(e) {return Response.json({ok:false,error:e.message})}
        }}
      ` },
      { type: 'ESModule', path: 'connector.mjs', contents: source },
    ],
    compatibilityDate: '2026-05-01',
    outboundService: async request => {
      requests.push({url:request.url, auth:request.headers.get('authorization')});
      if (request.url.endsWith('/redirect') || request.url.includes('oaiusercontent.com'))
        return new Response(null, {status:302, headers:{Location:'https://untrusted.example/collect'}});
      return Response.json({role:'agent',identity:'agent:'+'a'.repeat(32)});
    },
  });
  try {
    const good = await (await mf.dispatchFetch('http://local/ok')).json();
    assert.equal(good.ok, true, JSON.stringify(good));
    assert.equal(good.result.role, 'agent');
    const redirected = await (await mf.dispatchFetch('http://local/redirect')).json();
    assert.match(redirected.error, /Gateway redirect blocked/);
    const image = await (await mf.dispatchFetch('http://local/image')).json();
    assert.match(image.error, /Image redirect blocked/);
    assert.equal(requests.length, 3);
    assert.equal(requests[0].auth, 'Bearer '+token);
    assert.equal(requests[2].auth, null);
    assert.ok(requests.every(r => !r.url.includes('untrusted.example')));
  } finally {await mf.dispose()}
});
