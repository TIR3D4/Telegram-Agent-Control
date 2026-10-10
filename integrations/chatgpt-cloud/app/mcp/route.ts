import { env } from "cloudflare:workers";
import { rpc } from "../../lib/connector.mjs";
export const dynamic = "force-dynamic";
export async function POST(request: Request) {
  return rpc(request, env);
}
