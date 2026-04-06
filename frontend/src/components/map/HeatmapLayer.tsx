'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useMapStore } from '@/stores/mapStore';
import { Deck } from '@deck.gl/core';
import { HeatmapLayer as DeckHeatmapLayer } from '@deck.gl/aggregation-layers';
import { fetchHeatmapAll } from '@/lib/api';

interface HeatmapLayerProps {
  mapInstance: React.RefObject<any>;
}

const COLOR_RANGE: [number, number, number][] = [
  [1, 152, 189],
  [73, 227, 206],
  [216, 254, 181],
  [254, 237, 177],
  [254, 173, 84],
  [209, 55, 78],
];

/** Convert Kakao Map state → deck.gl WebMercator viewport params */
function getViewState(map: any) {
  const center = map.getCenter();
  const level = map.getLevel();
  // Kakao level → approximate zoom: level 1 ≈ zoom 21, each level doubles scale
  const zoom = 21 - level;
  return {
    longitude: center.getLng(),
    latitude: center.getLat(),
    zoom,
    pitch: 0,
    bearing: 0,
  };
}

export default function HeatmapLayer({ mapInstance }: HeatmapLayerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const deckRef = useRef<Deck | null>(null);
  const {
    heatmapEnabled,
    heatmapTimeSlot,
    heatmapData,
    heatmapLoading,
    setHeatmapData,
    setHeatmapLoading,
  } = useMapStore();

  // Load heatmap data on enable
  useEffect(() => {
    if (!heatmapEnabled || heatmapData) return;

    let cancelled = false;
    setHeatmapLoading(true);

    fetchHeatmapAll()
      .then((result) => {
        if (!cancelled) {
          setHeatmapData(result.slots);
          setHeatmapLoading(false);
        }
      })
      .catch((err) => {
        console.error('[Heatmap] Failed to load data:', err);
        if (!cancelled) setHeatmapLoading(false);
      });

    return () => { cancelled = true; };
  }, [heatmapEnabled, heatmapData, setHeatmapData, setHeatmapLoading]);

  // Sync deck.gl viewport with Kakao Map
  const syncViewport = useCallback(() => {
    const map = mapInstance.current;
    const deck = deckRef.current;
    if (!map || !deck) return;

    deck.setProps({
      viewState: getViewState(map),
    });
  }, [mapInstance]);

  // Initialize and teardown deck.gl
  useEffect(() => {
    const map = mapInstance.current;
    if (!heatmapEnabled || !map || !canvasRef.current) {
      // Cleanup
      if (deckRef.current) {
        deckRef.current.finalize();
        deckRef.current = null;
      }
      return;
    }

    const deck = new Deck({
      canvas: canvasRef.current,
      initialViewState: getViewState(map),
      controller: false,
      layers: [],
      getTooltip: undefined,
      style: { pointerEvents: 'none' },
    });
    deckRef.current = deck;

    // Listen for Kakao Map viewport changes
    const events = ['center_changed', 'zoom_changed', 'idle'];
    events.forEach((evt) => {
      window.kakao.maps.event.addListener(map, evt, syncViewport);
    });

    return () => {
      events.forEach((evt) => {
        window.kakao.maps.event.removeListener(map, evt, syncViewport);
      });
      deck.finalize();
      deckRef.current = null;
    };
  }, [heatmapEnabled, mapInstance, syncViewport]);

  // Update heatmap layer when data or time slot changes
  useEffect(() => {
    const deck = deckRef.current;
    if (!deck || !heatmapData) return;

    const points = heatmapData[String(heatmapTimeSlot)] || [];

    const layer = new DeckHeatmapLayer({
      id: 'heatmap-layer',
      data: points,
      getPosition: (d: any) => [d.lng, d.lat],
      getWeight: (d: any) => d.weight,
      radiusPixels: 60,
      intensity: 1,
      threshold: 0.05,
      colorRange: COLOR_RANGE,
      aggregation: 'SUM',
    });

    deck.setProps({ layers: [layer] });
  }, [heatmapData, heatmapTimeSlot]);

  // Sync once when deck.gl first renders
  useEffect(() => {
    if (deckRef.current) syncViewport();
  }, [heatmapData, syncViewport]);

  if (!heatmapEnabled) return null;

  return (
    <>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full pointer-events-none"
        style={{ zIndex: 5 }}
      />
      {heatmapLoading && (
        <div
          className="absolute top-16 left-1/2 -translate-x-1/2 bg-black/70 text-white text-xs px-3 py-1.5 rounded-full"
          style={{ zIndex: 15 }}
        >
          히트맵 데이터 로딩 중...
        </div>
      )}
    </>
  );
}
