'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import RoleSelector from './RoleSelector';
import HeroVisual from './HeroVisual';
import {
  DEFAULT_HERO_LEAD,
  DEFAULT_HERO_SUB,
  DEFAULT_STARTER_CHIPS,
  ROLES,
  Role,
  isValidRole,
} from './roles';

const LS_KEY = 'ms_role';

export default function Hero() {
  const router = useRouter();
  const [role, setRole] = useState<Role | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
    try {
      const stored = window.localStorage.getItem(LS_KEY);
      if (isValidRole(stored)) setRole(stored);
    } catch {
      // localStorage unavailable — keep default
    }
  }, []);

  const handleSelectRole = (r: Role | null) => {
    setRole(r);
    try {
      if (r) window.localStorage.setItem(LS_KEY, r);
      else window.localStorage.removeItem(LS_KEY);
    } catch {
      // ignore
    }
  };

  const lead = role ? ROLES[role].heroLead : DEFAULT_HERO_LEAD;
  const sub = role ? ROLES[role].heroSub : DEFAULT_HERO_SUB;
  const chips = role ? ROLES[role].starterChips : DEFAULT_STARTER_CHIPS;

  const goToApp = (prefill?: string) => {
    const params = new URLSearchParams();
    if (role) params.set('role', role);
    if (prefill) params.set('q', prefill);
    const qs = params.toString();
    router.push(qs ? `/app?${qs}` : '/app');
  };

  return (
    <section
      data-testid="hero-section"
      className="px-6 py-16 lg:py-24"
      style={{ backgroundColor: 'var(--bg-primary)' }}
    >
      <div className="max-w-6xl mx-auto grid gap-12 lg:grid-cols-[1.1fr,1fr] lg:items-center">
        <div>
          <div
            className="inline-flex items-center gap-1.5 mb-6 px-3 py-1 rounded-full text-xs font-semibold"
            style={{
              backgroundColor: 'color-mix(in srgb, var(--brand-teal) 15%, transparent)',
              color: 'var(--brand-teal)',
            }}
          >
            BETA · 베타 기간 무료
          </div>

          <h1
            data-testid="hero-headline"
            className="text-4xl lg:text-6xl font-black tracking-tight leading-tight mb-4 break-keep"
            style={{
              color: 'var(--text-primary)',
              fontFeatureSettings: '"ss06"',
            }}
          >
            {lead}
          </h1>
          <p
            className="text-base lg:text-lg mb-8 max-w-xl"
            style={{ color: 'var(--text-secondary)' }}
          >
            {sub}
          </p>

          <div className="mb-8" suppressHydrationWarning={!hydrated}>
            <RoleSelector selected={role} onSelect={handleSelectRole} />
          </div>

          <div
            className="flex flex-wrap gap-2 mb-8"
            data-testid="starter-chips"
          >
            {chips.map((chip, idx) => (
              <button
                key={`${idx}-${chip.slice(0, 12)}`}
                type="button"
                data-testid={`starter-chip-${idx}`}
                onClick={() => goToApp(chip)}
                className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-all hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                }}
              >
                {chip}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              data-testid="hero-primary-cta"
              onClick={() => goToApp()}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-base transition-transform hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              style={{
                backgroundColor: 'var(--brand-deep-blue)',
                color: '#ffffff',
              }}
            >
              지도에서 시작하기 <span aria-hidden>→</span>
            </button>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-base transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              style={{
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
              }}
            >
              어떻게 쓰나요?
            </a>
          </div>
        </div>

        <div>
          <HeroVisual />
        </div>
      </div>
    </section>
  );
}
