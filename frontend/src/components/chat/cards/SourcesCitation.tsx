'use client';

import { useState } from 'react';
import { DataSourceInfo } from '@/lib/types';

interface SourcesCitationProps {
  sources?: DataSourceInfo[];
  quarter?: string;
  extraFooterText?: string;
}

export default function SourcesCitation({ sources, quarter, extraFooterText }: SourcesCitationProps) {
  const [expanded, setExpanded] = useState(false);

  const isMock = sources?.length === 1 && sources[0].id === 'mock';
  const hasSources = sources && sources.length > 0 && !isMock;

  // Deduplicate sources by id
  const uniqueSources = hasSources
    ? sources.filter((s, i, arr) => arr.findIndex((x) => x.id === s.id) === i)
    : [];

  // Primary platform name for collapsed display
  const primaryPlatform = uniqueSources.length > 0 ? uniqueSources[0].platform : '';

  return (
    <div className="px-4 py-2" style={{ backgroundColor: 'var(--bg-tertiary)', borderTop: '1px solid var(--border-color)' }}>
      {/* Collapsed line */}
      <div className="flex items-center justify-between">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {quarter && <>{'데이터 기준: '}{quarter}</>}
          {isMock && <>{quarter ? '  ·  ' : ''}{'출처: 샘플 데이터'}</>}
          {hasSources && (
            <>
              {'  ·  출처: '}
              {primaryPlatform}
              {' '}({uniqueSources.length})
            </>
          )}
        </p>
        {hasSources && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs ml-2 flex-shrink-0 focus:outline-none"
            style={{ color: 'var(--text-muted)' }}
            aria-label={expanded ? '출처 접기' : '출처 펼치기'}
          >
            {expanded ? '\u25B2' : '\u25BC'}
          </button>
        )}
      </div>

      {/* Expanded detail */}
      {expanded && hasSources && (
        <div className="mt-1.5 space-y-0.5">
          {uniqueSources.map((source, i) => {
            const isLast = i === uniqueSources.length - 1;
            const marker = isLast ? '\u2514' : '\u251C';
            return (
              <p key={source.id} className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {'  '}{marker} {source.name} ({source.api_endpoint})
              </p>
            );
          })}
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {'  '}{uniqueSources[0].organization} · {uniqueSources[0].license}
          </p>
          <a
            href={uniqueSources[0].url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs underline block"
            style={{ color: 'var(--text-muted)' }}
          >
            {'  '}{uniqueSources[0].url.replace('https://', '')}
          </a>
        </div>
      )}

      {/* Extra footer text (e.g. disclaimers, analysis count) */}
      {extraFooterText && (
        <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
          {extraFooterText}
        </p>
      )}
    </div>
  );
}
