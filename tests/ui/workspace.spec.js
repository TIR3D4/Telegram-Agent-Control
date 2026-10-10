const {test,expect}=require('@playwright/test');
async function login(page){
 await page.goto('/');await page.locator('#username').fill('ui-owner');await page.locator('#password').fill('ui-password-for-tests');await page.locator('#password-form button').click();await expect(page.locator('.workspace-hero')).toBeVisible();
}
test('connection center exports safe configs and performs actual MCP protocol check',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));await login(page);
 await page.locator('[data-view="connections"]').click();
 for(const id of ['api','mcp','codex','claude','chatgpt']){
   await page.locator('[data-profile="'+id+'"]').click();
   await expect(page.locator('#connection-url')).toHaveValue(/127\.0\.0\.1:8790/);
 }
 await page.locator('#connection-test-token').fill('ui-test-agent-'+'x'.repeat(40));
 await page.locator('#connection-test').click();
 await expect(page.locator('#connection-evidence')).toContainText('REST تأیید شد');
 await expect(page.locator('#connection-evidence')).toContainText('ابزار');
 await expect(page.locator('#connection-test-token')).toHaveValue('');
 await page.locator('#connection-test-token').fill('ui-test-owner-'+'x'.repeat(40));
 await page.locator('#connection-test').click();
 await expect(page.locator('#connection-evidence')).toContainText('کلید مالک پذیرفته نیست');
 await page.screenshot({path:`test-results/connections-${test.info().project.name}.png`,fullPage:true});
 expect(errors).toEqual([]);
});
test('visual photo composer binds upload and cannot publish before independent approval',async({page,request})=>{
 await login(page);await page.locator('[data-view="compose"]').click();
 await page.locator('#post-text').fill('تست پیش‌نویس تصویری؛ ارسال نشود');
 await page.locator('#post-file').setInputFiles({name:'pixel.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1cAAAAASUVORK5CYII=','base64')});
 await expect(page.locator('#post-upload-status')).toContainText('آماده');
 await page.locator('#post-button-1').fill('تست');await page.locator('#post-url-1').fill('https://t.me/example');
 await page.locator('#post-time').fill('2027-01-02T12:00');
 await expect(page.locator('#visual-post-image')).toBeVisible();
 await page.screenshot({path:`test-results/composer-${test.info().project.name}.png`,fullPage:true});
 await page.locator('#post-save').click();await expect(page.locator('#detail')).toBeVisible();
 const pre=await page.locator('#detail-body pre').textContent();const op=JSON.parse(pre);
 expect(op.method).toBe('sendPhoto');expect(op.status).toBe('draft');expect(op.attempts).toBe(0);expect(op.attachments.photo).toMatch(/^[a-f0-9]{32}$/);
 expect(op.payload.reply_markup.inline_keyboard[0][0].url).toBe('https://t.me/example');
 const denied=await request.post('/v1/operations/'+op.id+'/approve',{headers:{Authorization:'Bearer '+'ui-test-agent-'+'x'.repeat(40)},data:{expected_digest:op.digest}});expect(denied.status()).toBe(403);
 await page.locator('#close-detail').click();await page.locator('#post-save').click();
 const same=JSON.parse(await page.locator('#detail-body pre').textContent());expect(same.id).toBe(op.id);
});
test('mobile overview fits viewport and optional chat is not the default',async({page})=>{
 await page.setViewportSize({width:390,height:844});await login(page);
 await expect(page.locator('.workspace-hero')).toBeVisible();await expect(page.locator('.assistant')).toHaveCount(0);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:`test-results/workspace-${test.info().project.name}.png`,fullPage:true});
});
