import { NextResponse } from 'next/server';

export const revalidate = 0;

export async function GET() {
  // Products API removed — return 410 Gone
  return NextResponse.json({ error: 'Products API removed' }, { status: 410 });
}

