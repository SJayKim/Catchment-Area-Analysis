'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { fetchDistricts } from '@/lib/api';
import { useDistrictStore } from '@/stores/districtStore';
import { useMapStore } from '@/stores/mapStore';
import { District } from '@/lib/types';

export default function Toolbar() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<District[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const select = useDistrictStore((s) => s.select);
  const isCompareMode = useDistrictStore((s) => s.isCompareMode);
  const toggleCompareMode = useDistrictStore((s) => s.toggleCompareMode);
  const compareList = useDistrictStore((s) => s.compareList);
  const addToCompare = useDistrictStore((s) => s.addToCompare);
  const setView = useMapStore((s) => s.setView);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const handleSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    try {
      const districts = await fetchDistricts(searchQuery);
      setResults(districts.slice(0, 10));
      setShowDropdown(true);
    } catch {
      setResults([]);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => handleSearch(query), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, handleSearch]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (district: District) => {
    if (isCompareMode) {
      addToCompare(district);
    } else {
      select(district, 'map');
    }
    if (district.center) {
      setView(district.center, 5);
    }
    setQuery(district.name);
    setShowDropdown(false);
  };

  const handleLocate = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setView(
          { lat: pos.coords.latitude, lng: pos.coords.longitude },
          5
        );
      },
      () => {
        // Geolocation failed - stay at default
      }
    );
  };

  return (
    <div className="h-12 flex items-center px-4 gap-3 flex-shrink-0 z-10"
      style={{ backgroundColor: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)' }}>
      {/* Logo — clicking returns to landing */}
      <Link
        href="/"
        data-testid="toolbar-logo"
        className="text-lg font-bold whitespace-nowrap hover:opacity-80 transition-opacity"
        style={{ color: 'var(--brand-deep-blue)' }}
      >
        MarketScope AI
      </Link>

      {/* Search */}
      <div className="relative flex-1 max-w-md" ref={dropdownRef}>
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
            style={{ color: 'var(--text-muted)' }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="상권 검색..."
            className="w-full pl-10 pr-4 py-1.5 text-sm rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            style={{
              backgroundColor: 'var(--bg-tertiary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
            }}
          />
        </div>

        {/* Autocomplete Dropdown */}
        {showDropdown && results.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 rounded-lg shadow-lg max-h-64 overflow-y-auto z-50"
            style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
            {results.map((district) => (
              <button
                key={district.code}
                onClick={() => handleSelect(district)}
                className="w-full px-4 py-2 text-left text-sm flex items-center gap-2 transition-colors"
                style={{ color: 'var(--text-primary)' }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <span>{district.name}</span>
                <span className="text-xs px-1.5 py-0.5 rounded"
                  style={{ color: 'var(--text-muted)', backgroundColor: 'var(--bg-tertiary)' }}>
                  {district.type}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Current Location Button */}
      <button
        onClick={handleLocate}
        className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg transition-colors hover:opacity-80"
        style={{ color: 'var(--text-secondary)' }}
        title="현재 위치"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
        <span className="hidden sm:inline">내 위치</span>
      </button>

      {/* Compare Mode Toggle */}
      <button
        onClick={toggleCompareMode}
        className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg transition-colors ${
          isCompareMode
            ? 'bg-indigo-100 text-indigo-700 border border-indigo-300'
            : ''
        }`}
        style={!isCompareMode ? { color: 'var(--text-secondary)' } : undefined}
        title="비교모드"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
        <span className="hidden sm:inline">비교모드</span>
        {isCompareMode && compareList.length > 0 && (
          <span className="bg-indigo-500 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center">
            {compareList.length}
          </span>
        )}
      </button>
    </div>
  );
}
