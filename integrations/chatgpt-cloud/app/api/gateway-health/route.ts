import { env } from 'cloudflare:workers';
import { baseURL, readLimited } from '../../../lib/connector.mjs';
export const dynamic = 'force-dynamic';

// Private Sites access still applies. No user records, credential or Telegram call.
export async function GET() {
  try {
    const r = await fetch(baseURL(env) + '/health/ready', {
      redirect: 'manual', signal: AbortSignal.timeout(10000),
    });
    const json = (body: unknown, status = 200) => Response.json(body, {
      status, headers: {'Cache-Control': 'no-store'},
    });
    if (!r.ok || !r.headers.get('content-type')?.includes('application/json'))
      return json({reachable: false, ready: false, http_status: r.status}, 502);
    const result = JSON.parse(new TextDecoder().decode(await readLimited(r, 2048)));
    return json({reachable: true, ready: result.status === 'ready', http_status: r.status});
  } catch {
    return Response.json({reachable: false, ready: false, error: 'gateway_health_unavailable'}, {
      status: 502, headers: {'Cache-Control': 'no-store'},
    });
  }
}
