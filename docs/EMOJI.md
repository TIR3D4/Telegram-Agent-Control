# Visual emoji catalog

Import a public custom emoji set by submitting `getStickerSet` with its short name. On success the worker indexes `custom_emoji_id`, fallback emoji, pack, file ID and actual format. Sending the same import again updates metadata without replacing labels.

1. `GET /v1/emojis?pack=...` lists indexed entries, with pagination.
2. `POST /v1/emojis/{id}/preview` downloads the original through Telegram and renders a preview.
3. Inspect the actual PNG/WebP through the console, authenticated asset endpoint or MCP `emoji_image`.
4. `PATCH /v1/emojis/{id}` stores `description`, `tags`, `style`, `reviewed`.
5. `PUT /v1/emoji-roles/{role}` binds a reviewed ID to a stable purpose such as `support` or `payment_success`.

A fallback ✅ does not describe the custom artwork. Choose by the preview, not ID digits or the fallback alone. Catalog search is stored-label matching; the external multimodal agent supplies semantic judgment. No claim is made that the server independently understands images.

Static WebP previews use Pillow; WebM uses FFmpeg; TGS uses a resource-limited Lottie child process. A first-frame preview may be blank or miss animated meaning. Retrieve the original asset and inspect the animation before selecting ambiguous artwork. Conversion failures remain explicit on the entry and never substitute an unrelated image.

Premium custom emoji permissions depend on the bot and destination. Owner Premium alone does not grant unrestricted channel usage. Inline buttons support the official `icon_custom_emoji_id` and style fields when eligible. The API does not silently add undocumented prefixes or replace premium icons. Validate and test the intended context.

Pack artwork belongs to its respective creators. Import is private to your installation; the public repository includes no third-party emoji packs. IDs are strings to preserve 64-bit precision in JavaScript clients.
