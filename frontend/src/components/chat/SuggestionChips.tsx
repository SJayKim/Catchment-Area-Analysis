'use client';

interface SuggestionChipsProps {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
  disabled: boolean;
}

export default function SuggestionChips({
  suggestions,
  onSelect,
  disabled,
}: SuggestionChipsProps) {
  if (suggestions.length === 0) return null;

  return (
    <div className="px-4 pb-2 flex-shrink-0">
      <div className="flex flex-wrap gap-2">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => onSelect(suggestion)}
            disabled={disabled}
            className="text-xs px-3 py-1.5 rounded-full disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap hover:opacity-80"
            style={{
              backgroundColor: 'var(--thinking-bg)',
              color: 'var(--bg-accent)',
              border: '1px solid var(--border-color)',
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
