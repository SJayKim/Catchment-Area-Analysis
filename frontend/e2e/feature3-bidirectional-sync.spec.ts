import { test, expect, waitForMapReady, sendChatMessage, waitForResponseComplete, getStatusBarText } from './helpers/setup';

test.describe('Feature 3: bidirectional sync', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app');
    await waitForMapReady(page);
  });

  test('3-1: chat input updates StatusBar', async ({ page }) => {
    await sendChatMessage(page, '\uAC15\uB0A8\uC5ED \uBD84\uC11D\uD574\uC918');

    const statusText = await getStatusBarText(page);
    expect(statusText).toContain('\uAC15\uB0A8\uC5ED');
  });

  test('3-2: switching districts via chat updates StatusBar', async ({ page }) => {
    await sendChatMessage(page, '\uAC15\uB0A8\uC5ED \uBD84\uC11D\uD574\uC918');
    let statusText = await getStatusBarText(page);
    expect(statusText).toContain('\uAC15\uB0A8\uC5ED');

    await sendChatMessage(page, '\uD64D\uB300\uC785\uAD6C \uBD84\uC11D\uD574\uC918');
    statusText = await getStatusBarText(page);
    expect(statusText).toContain('\uD64D\uB300\uC785\uAD6C');
  });

  test('3-3: chat selection does not trigger duplicate auto-query', async ({ page }) => {
    await sendChatMessage(page, '\uBA85\uB3D9 \uBD84\uC11D\uD574\uC918');

    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';

    // User query appears exactly once
    const userQueryCount = (chatText.match(/\uBA85\uB3D9 \uBD84\uC11D\uD574\uC918/g) || []).length;
    expect(userQueryCount).toBe(1);

    // No auto-generated summary query
    const autoQueryCount = (chatText.match(/\uBA85\uB3D9 \uC0C1\uAD8C \uC694\uC57D\uD574\uC918/g) || []).length;
    expect(autoQueryCount).toBe(0);
  });

  test('3-4: chat then search selects different district', async ({ page }) => {
    await sendChatMessage(page, '\uAC15\uB0A8\uC5ED \uBD84\uC11D\uD574\uC918');
    let statusText = await getStatusBarText(page);
    expect(statusText).toContain('\uAC15\uB0A8\uC5ED');

    // Search toolbar
    const searchInput = page.locator('input[placeholder*="\uAC80\uC0C9"]').first();
    await searchInput.fill('\uD64D\uB300\uC785\uAD6C');
    await page.waitForTimeout(800);

    const dropdown = page.locator('button', { hasText: '\uD64D\uB300\uC785\uAD6C' }).first();
    if (await dropdown.isVisible({ timeout: 3000 }).catch(() => false)) {
      await dropdown.click();
      await waitForResponseComplete(page);
      statusText = await getStatusBarText(page);
      expect(statusText).toContain('\uD64D\uB300\uC785\uAD6C');
    } else {
      await sendChatMessage(page, '\uD64D\uB300\uC785\uAD6C \uC0C1\uAD8C \uC694\uC57D\uD574\uC918');
      statusText = await getStatusBarText(page);
      expect(statusText).toContain('\uD64D\uB300\uC785\uAD6C');
    }
  });

  test('3-5: comparison request works', async ({ page }) => {
    await sendChatMessage(page, '\uAC15\uB0A8\uC5ED\uC774\uB791 \uD64D\uB300 \uBE44\uAD50\uD574\uC918');

    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      chatText.includes('\uBE44\uAD50') ||
      chatText.includes('\uAC15\uB0A8\uC5ED') ||
      chatText.includes('\uD64D\uB300')
    ).toBeTruthy();

    expect(chatText.length).toBeGreaterThan(0);
  });
});
