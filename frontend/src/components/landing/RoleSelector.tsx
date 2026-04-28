'use client';

import { ROLES, Role } from './roles';

interface Props {
  selected: Role | null;
  onSelect: (role: Role | null) => void;
}

export default function RoleSelector({ selected, onSelect }: Props) {
  return (
    <div
      className="flex flex-wrap items-center gap-3"
      role="radiogroup"
      aria-label="어떤 역할이신가요?"
      data-testid="role-selector"
    >
      <span
        className="text-sm font-medium mr-1"
        style={{ color: 'var(--text-secondary)' }}
      >
        어떤 역할이신가요?
      </span>
      {(Object.values(ROLES) as ReturnType<typeof Object.values> as typeof ROLES[Role][]).map(
        (r) => {
          const active = selected === r.id;
          return (
            <button
              key={r.id}
              type="button"
              role="radio"
              aria-checked={active}
              data-testid={`role-chip-${r.id}`}
              onClick={() => onSelect(active ? null : r.id)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium transition-all"
              style={{
                backgroundColor: active
                  ? 'var(--brand-deep-blue)'
                  : 'var(--bg-secondary)',
                color: active ? '#ffffff' : 'var(--text-primary)',
                border: `1px solid ${active ? 'var(--brand-deep-blue)' : 'var(--border-color)'}`,
              }}
            >
              <r.Icon size={16} strokeWidth={1.75} aria-hidden />
              {r.label}
            </button>
          );
        }
      )}
    </div>
  );
}
