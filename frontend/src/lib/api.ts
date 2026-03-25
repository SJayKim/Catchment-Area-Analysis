import { District, MapBounds, PolygonFeature } from './types';

const API_BASE = '/api';

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
  return res.json();
}

export async function fetchDistrictDetail(code: string): Promise<District> {
  const res = await fetch(`${API_BASE}/districts/${code}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch district detail: ${res.status}`);
  }
  return res.json();
}

export async function fetchPolygons(bounds: MapBounds): Promise<PolygonFeature[]> {
  const params = new URLSearchParams({
    sw_lat: bounds.sw_lat.toString(),
    sw_lng: bounds.sw_lng.toString(),
    ne_lat: bounds.ne_lat.toString(),
    ne_lng: bounds.ne_lng.toString(),
  });

  const res = await fetch(`${API_BASE}/map-data/polygons?${params}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch polygons: ${res.status}`);
  }
  return res.json();
}

export async function sendChatMessage(
  message: string,
  sessionId: string,
  districtCode?: string
): Promise<Response> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      district_code: districtCode,
    }),
  });

  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`);
  }

  return res;
}
