import { env } from "cloudflare:workers";
import {
  connection,
  saveConnection,
  readLimited,
  SafeError,
} from "../../../lib/connector.mjs";
export const dynamic = "force-dynamic";
const json = (v: unknown, status = 200) =>
  Response.json(v, { status, headers: { "Cache-Control": "no-store" } });
export async function GET(r: Request) {
  const user = r.headers.get("oai-authenticated-user-id");
  if (!user) return json({ error: "Sign in required" }, 401);
  try {
    return json({ connected: !!(await connection(env, user)) });
  } catch {
    return json({ error: "Connection storage unavailable" }, 503);
  }
}
export async function POST(r: Request) {
  const user = r.headers.get("oai-authenticated-user-id");
  if (!user) return json({ error: "Sign in required" }, 401);
  if (r.headers.get("origin") !== new URL(r.url).origin)
    return json({ error: "Same-origin browser form required" }, 403);
  try {
    const body = JSON.parse(
      new TextDecoder().decode(await readLimited(r, 2048)),
    );
    return json(await saveConnection(env, user, body.agent_key));
  } catch (e) {
    return json(
      { error: e instanceof SafeError ? e.message : "Connection not saved" },
      400,
    );
  }
}
export async function DELETE(r: Request) {
  const user = r.headers.get("oai-authenticated-user-id");
  if (!user) return json({ error: "Sign in required" }, 401);
  if (r.headers.get("origin") !== new URL(r.url).origin)
    return json({ error: "Same-origin browser form required" }, 403);
  await (env as any).DB.prepare("DELETE FROM connections WHERE user_id = ?")
    .bind(user)
    .run();
  return json({ connected: false });
}
