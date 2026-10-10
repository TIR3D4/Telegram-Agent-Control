import { env } from "cloudflare:workers";
import { tokenFor, uploadImage, SafeError } from "../../../lib/connector.mjs";
export const dynamic = "force-dynamic";
export async function POST(r: Request) {
  const user = r.headers.get("oai-authenticated-user-id");
  if (!user || r.headers.get("origin") !== new URL(r.url).origin)
    return Response.json(
      { error: "Signed-in browser required" },
      { status: 403 },
    );
  // Bound streamed multipart before parsing, including requests without Content-Length.
  try {
    const { readLimited } = await import("../../../lib/connector.mjs");
    const bytes = await readLimited(r, 11 * 1024 * 1024);
    const form = await new Response(bytes, {
      headers: { "Content-Type": r.headers.get("content-type") || "" },
    }).formData();
    const file = form.get("file");
    if (!(file instanceof File)) throw new SafeError("Choose an image");
    const data = await uploadImage(
      env,
      await tokenFor(env, user),
      new Uint8Array(await file.arrayBuffer()),
      file.type,
      file.name,
    );
    return Response.json(data, { headers: { "Cache-Control": "no-store" } });
  } catch (e) {
    return Response.json(
      { error: e instanceof SafeError ? e.message : "Upload failed" },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }
}
