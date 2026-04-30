/**
 * Ring0-F1/F2 — Tier hook + FeatureGate stubs.
 *
 * 2026-04-30 Plan `ux-sweep-phase-f-tier-hook`. Phase 2 머지 전 surface diff 최소화
 * 위해 박아둔 stub. 본 spec 은 정적 소스 invariants 만 회귀 — 컴파일 가능 + 현재
 * 단계의 no-op 의미 보장 (tier === 'free' 하드코딩 + FeatureGate children 통과).
 */
import { test, expect } from '../helpers/setup';

test.describe('Ring0-F — Tier hook (Phase F stub)', () => {
  test('Ring0-F1 — useTier 하드코딩 free 반환 + Tier 타입 export', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const target = path.resolve(process.cwd(), 'src/hooks/useTier.ts');
    const src = fs.readFileSync(target, 'utf8');
    expect(src).toMatch(/export\s+type\s+Tier\s*=\s*['"]free['"]\s*\|\s*['"]pro['"]\s*\|\s*['"]team['"]/);
    expect(src).toMatch(/export\s+function\s+useTier\s*\(\s*\)/);
    // 현재 stub 단계: tier 값 'free' 하드코딩 보장.
    expect(src).toMatch(/tier:\s*['"]free['"]/);
    expect(src).toMatch(/isLoading:\s*false/);
  });

  test('Ring0-F2 — FeatureGate no-op (children 그대로 렌더)', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const target = path.resolve(
      process.cwd(),
      'src/components/common/FeatureGate.tsx',
    );
    const src = fs.readFileSync(target, 'utf8');
    expect(src).toContain("'use client'");
    expect(src).toMatch(/import\s*{\s*useTier[^}]*}\s*from\s*['"]@\/hooks\/useTier['"]/);
    // children 그대로 반환하는 fragment — Phase 2 머지 전까지 게이팅 비활성.
    expect(src).toMatch(/return\s*<>\s*{\s*children\s*}\s*<\/>/);
  });

  // (Mock-only) 신규 14 — Plan UX Sweep Phase F: useTier 가 server component 에
  // 서 import 되어도 컴파일 에러가 발생하지 않도록 'use client' directive 가
  // **부재** 해야 함 (hook 자체는 type+function export only). FeatureGate 만
  // 'use client'.
  test('Ring0-F1-SSR — useTier.ts 는 server-component-friendly (no use client)', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const target = path.resolve(process.cwd(), 'src/hooks/useTier.ts');
    const src = fs.readFileSync(target, 'utf8');
    // useTier.ts 자체는 'use client' directive 가 없어야 — server component
    // 에서 type Tier import 가 가능하도록.
    expect(src).not.toMatch(/^['"]use client['"]/m);
    // 단, 함수 형태로 export 되어 client 측 hook 호출이 가능해야 한다.
    expect(src).toMatch(/export\s+function\s+useTier/);
    // type Tier 도 함께 export 되어 있어야 server side 에서 type-only import 가능.
    expect(src).toMatch(/export\s+type\s+Tier/);
  });

  // (Mock-only) 신규 15 — Plan UX Sweep Phase F: FeatureGate 의 import 사용처가
  // 0개여야 (Phase 2 머지 전까지 surface 활성 X). 사용처 발견 시 Phase 2 까지
  // 거꾸로 surface 노출 — 회귀.
  test('Ring0-F2-IMPORT-MAP — FeatureGate import 사용처 0 (Phase 2 머지 전)', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const root = path.resolve(process.cwd(), 'src');

    // 재귀 walker — node_modules / .next 회피 + tsx/ts 파일만.
    function walk(dir: string): string[] {
      const out: string[] = [];
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const e of entries) {
        const full = path.join(dir, e.name);
        if (e.isDirectory()) {
          if (e.name === 'node_modules' || e.name === '.next') continue;
          out.push(...walk(full));
        } else if (/\.(ts|tsx)$/.test(e.name)) {
          out.push(full);
        }
      }
      return out;
    }
    const files = walk(root);
    const importRegex =
      /from\s+['"](@\/components\/common\/FeatureGate|\.\.?\/.*FeatureGate)['"]/;
    const hits: string[] = [];
    for (const f of files) {
      // 정의 파일 자체는 제외.
      if (f.endsWith(path.join('common', 'FeatureGate.tsx'))) continue;
      const src = fs.readFileSync(f, 'utf8');
      if (importRegex.test(src)) hits.push(f);
    }
    expect(hits, `FeatureGate 사용처: ${hits.join(', ')}`).toEqual([]);
  });
});
