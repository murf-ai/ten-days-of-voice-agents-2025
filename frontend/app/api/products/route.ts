import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';

export const revalidate = 0; // Don't cache

export async function GET() {
  try {
    // Read products.json from backend directory
    // Try multiple possible paths
    const possiblePaths = [
      join(process.cwd(), '..', 'backend', 'products.json'),
      join(process.cwd(), 'backend', 'products.json'),
      join(__dirname, '..', '..', '..', 'backend', 'products.json'),
    ];

    let products;
    let lastError;

    for (const productsPath of possiblePaths) {
      try {
        const fileContents = await readFile(productsPath, 'utf-8');
        products = JSON.parse(fileContents);
        break;
      } catch (err) {
        lastError = err;
        continue;
      }
    }

    if (!products) {
      console.error('Could not find products.json in any expected location:', lastError);
      return NextResponse.json(
        { error: 'Failed to load products' },
        { status: 500 }
      );
    }

    return NextResponse.json(products, {
      headers: {
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    console.error('Error reading products:', error);
    return NextResponse.json(
      { error: 'Failed to load products' },
      { status: 500 }
    );
  }
}

