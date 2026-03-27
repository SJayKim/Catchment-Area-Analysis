import { NextResponse } from 'next/server';

export async function GET() {
  const appKey = process.env.NEXT_PUBLIC_KAKAO_MAP_KEY;
  const sdkUrl = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${appKey}&autoload=false`;

  const res = await fetch(sdkUrl);
  const script = await res.text();

  return new NextResponse(script, {
    headers: {
      'Content-Type': 'application/javascript; charset=utf-8',
      'Cache-Control': 'public, max-age=86400',
    },
  });
}
