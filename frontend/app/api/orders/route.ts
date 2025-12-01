import { NextResponse } from 'next/server';
import { NextResponse } from 'next/server';

export const revalidate = 0;

export async function GET() {
  // Orders API removed — return 410 Gone
  return NextResponse.json({ error: 'Orders API removed' }, { status: 410 });
}
    return NextResponse.json(orders, {
      headers: {
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    console.error('Error reading orders:', error);
    // Return empty array on error instead of 500
    return NextResponse.json([], {
      headers: {
        'Cache-Control': 'no-store',
      },
    });
  }
}

