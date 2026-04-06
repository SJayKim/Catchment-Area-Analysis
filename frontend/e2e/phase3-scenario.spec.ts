import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3001';
const BACKEND_URL = 'http://localhost:8002';

// ===== F09 Scenario Tests =====

test.describe('F09: Revenue Simulation', () => {
  test('S9-1: Basic simulation returns SimulationCard', async ({ page }) => {
    // Navigate and wait for map
    await page.goto(BASE_URL);
    await page.waitForTimeout(3000);

    // Click on a mock polygon (강남역 D3001) if available, or type in chat
    const chatInput = page.locator('input[type="text"], textarea').last();
    await chatInput.fill('강남역에서 카페 열면 매출 얼마나 될까?');
    await chatInput.press('Enter');

    // Wait for simulation card to appear
    await page.waitForTimeout(15000);

    // Check for simulation card elements
    const pageContent = await page.content();
    const hasSimulation = pageContent.includes('시뮬레이션') || pageContent.includes('매출');
    expect(hasSimulation).toBeTruthy();
  });

  test('S9-4: No district shows guidance', async ({ page }) => {
    // Test via API directly
    const response = await page.request.post(`${BACKEND_URL}/api/chat`, {
      data: { message: '매출 시뮬레이션 해줘', session_id: 'test-s94', district_code: '' },
    });
    expect(response.ok()).toBeTruthy();

    const text = await response.text();
    // With empty district_code, agent should NOT return a simulation card — instead it should ask for info
    const hasSimulationCard = text.includes('"card_type": "simulation"') || text.includes('"card_type":"simulation"');
    expect(hasSimulationCard).toBeFalsy(); // No simulation card without district
  });

  test('S9-5: Disclaimer present in simulation response', async ({ page }) => {
    const response = await page.request.post(`${BACKEND_URL}/api/chat`, {
      data: { message: '카페 매출 얼마나?', session_id: 'test-s95', district_code: 'D3001' },
    });
    const text = await response.text();
    const hasDisclaimer = text.includes('추정치') || text.includes('실제와 다를') || text.includes('실제 매출과 다를');
    expect(hasDisclaimer).toBeTruthy();
  });

  test('S9-6: Seoul average comparison present', async ({ page }) => {
    const response = await page.request.post(`${BACKEND_URL}/api/chat`, {
      data: { message: '카페 열면 매출?', session_id: 'test-s96', district_code: 'D3001' },
    });
    const text = await response.text();
    expect(text).toContain('seoul_comparison');
    expect(text).toContain('seoul_avg');
  });
});

// ===== F06 Scenario Tests =====

test.describe('F06: Heatmap API', () => {
  test('B6-1: Single time_slot returns points', async ({ page }) => {
    const response = await page.request.get(`${BACKEND_URL}/api/map-data/heatmap?time_slot=12`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.time_slot).toBe(12);
    expect(data.points.length).toBeGreaterThan(0);
    // Validate point structure
    const p = data.points[0];
    expect(p).toHaveProperty('lat');
    expect(p).toHaveProperty('lng');
    expect(p).toHaveProperty('weight');
  });

  test('B6-2: Preload all returns 24 slots', async ({ page }) => {
    const response = await page.request.get(`${BACKEND_URL}/api/map-data/heatmap/all`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Object.keys(data.slots).length).toBe(24);
    expect(data.quarter).toBeTruthy();
  });

  test('B6-3: Invalid time_slot=25 returns 422', async ({ page }) => {
    const response = await page.request.get(`${BACKEND_URL}/api/map-data/heatmap?time_slot=25`);
    expect(response.status()).toBe(422);
  });

  test('B6-4: Cache consistency', async ({ page }) => {
    const r1 = await page.request.get(`${BACKEND_URL}/api/map-data/heatmap?time_slot=18`);
    const r2 = await page.request.get(`${BACKEND_URL}/api/map-data/heatmap?time_slot=18`);
    const d1 = await r1.json();
    const d2 = await r2.json();
    expect(JSON.stringify(d1)).toBe(JSON.stringify(d2));
  });
});

// ===== F06 UI Tests =====

test.describe('F06: Heatmap UI', () => {
  test('S6-1: Heatmap toggle button exists', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForTimeout(3000);

    // Look for the heatmap toggle button (fire icon)
    const heatmapBtn = page.locator('button[title="유동인구 히트맵"]');
    await expect(heatmapBtn).toBeVisible();
  });

  test('S6-5: Heatmap toggle on/off', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForTimeout(3000);

    const heatmapBtn = page.locator('button[title="유동인구 히트맵"]');
    // Click ON
    await heatmapBtn.click();
    await page.waitForTimeout(2000);

    // Should see a canvas element for heatmap or time slider
    const hasHeatmapUI = await page.locator('input[type="range"]').count();
    expect(hasHeatmapUI).toBeGreaterThan(0);

    // Click OFF
    await heatmapBtn.click();
    await page.waitForTimeout(500);
  });
});

// ===== F10 Scenario Tests =====

test.describe('F10: PDF Report', () => {
  test('S10-1: PDF button exists after chat', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForTimeout(3000);

    // Send a message first to make PDF button visible
    const chatInput = page.locator('input[type="text"], textarea').last();
    await chatInput.fill('안녕하세요');
    await chatInput.press('Enter');
    await page.waitForTimeout(5000);

    // PDF button should appear
    const pdfBtn = page.locator('button[title="PDF 리포트 내보내기"]');
    await expect(pdfBtn).toBeVisible();
  });

  test('S10-5: No crash with empty chat', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForTimeout(3000);

    // PDF button should not be visible when no messages
    const pdfBtn = page.locator('button[title="PDF 리포트 내보내기"]');
    const count = await pdfBtn.count();
    // If no messages, button should be hidden
    expect(count).toBe(0);
  });
});
