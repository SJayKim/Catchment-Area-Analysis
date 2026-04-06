import { District, MapBounds, PolygonFeature } from './types';

const API_BASE = '/api';
const CHAT_API_BASE = '/api';

export async function fetchDistricts(
  search?: string,
  type?: string
): Promise<District[]> {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (type) params.set('type', type);

  const query = params.toString();
  const url = `${API_BASE}/districts${query ? `?${query}` : ''}`;

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch districts: ${res.status}`);
  }

  const data = await res.json();
  const items = data.items || data;

  // Transform backend response → District[]
  return items.map((item: Record<string, any>) => ({
    code: item.district_code,
    name: item.district_name,
    type: item.district_type,
    center: { lat: item.center_lat, lng: item.center_lng },
    dataQuarter: item.data_quarter,
  }));
}

export async function fetchDistrictDetail(code: string): Promise<District> {
  const res = await fetch(`${API_BASE}/districts/${code}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch district detail: ${res.status}`);
  }
  return res.json();
}

export async function fetchPolygons(bounds: MapBounds): Promise<PolygonFeature[]> {
  const boundsStr = `${bounds.sw_lat},${bounds.sw_lng},${bounds.ne_lat},${bounds.ne_lng}`;
  const params = new URLSearchParams({ bounds: boundsStr });

  const res = await fetch(`${API_BASE}/map-data/polygons?${params}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch polygons: ${res.status}`);
  }

  const geojson = await res.json();

  // Transform GeoJSON FeatureCollection → PolygonFeature[]
  return (geojson.features || []).map((f: Record<string, any>) => ({
    code: f.properties.district_code,
    name: f.properties.district_name,
    type: f.properties.district_type,
    coordinates: f.geometry.coordinates[0], // outer ring
    center: f.properties.center
      ? { lat: f.properties.center[1], lng: f.properties.center[0] }
      : { lat: 0, lng: 0 },
  }));
}

export interface HeatmapPoint {
  lat: number;
  lng: number;
  weight: number;
}

export interface HeatmapAllData {
  quarter: string;
  slots: Record<string, HeatmapPoint[]>;
}

export async function fetchHeatmapAll(quarter?: string): Promise<HeatmapAllData> {
  const params = new URLSearchParams();
  if (quarter) params.set('quarter', quarter);

  const query = params.toString();
  const res = await fetch(`${API_BASE}/map-data/heatmap/all${query ? `?${query}` : ''}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch heatmap data: ${res.status}`);
  }
  return res.json();
}

export async function sendChatMessage(
  message: string,
  sessionId: string,
  districtCode?: string,
  signal?: AbortSignal
): Promise<Response> {
  const res = await fetch(`${CHAT_API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      district_code: districtCode,
    }),
    signal,
  });

  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`);
  }

  return res;
}
