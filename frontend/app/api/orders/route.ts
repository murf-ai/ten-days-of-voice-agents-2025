import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';

export const revalidate = 0; // Don't cache

export async function GET() {
  try {
    // Read orders.json from backend directory
    // Try multiple possible paths
    const possiblePaths = [
      join(process.cwd(), '..', 'backend', 'orders.json'),
      join(process.cwd(), 'backend', 'orders.json'),
      join(__dirname, '..', '..', '..', 'backend', 'orders.json'),
    ];

    let orders;
    let lastError;

    for (const ordersPath of possiblePaths) {
      try {
        // Check if file exists first
        const { access } = await import('fs/promises');
        try {
          await access(ordersPath);
        } catch {
          // File doesn't exist, return empty array
          return NextResponse.json([], {
            headers: {
              'Cache-Control': 'no-store',
            },
          });
        }
        
        const fileContents = await readFile(ordersPath, 'utf-8');
        // Handle empty file
        if (!fileContents.trim()) {
          return NextResponse.json([], {
            headers: {
              'Cache-Control': 'no-store',
            },
          });
        }
        orders = JSON.parse(fileContents);
        break;
      } catch (err) {
        lastError = err;
        continue;
      }
    }

    if (!orders) {
      // If file doesn't exist, return empty array instead of error
      console.log('Orders file not found, returning empty array');
      return NextResponse.json([], {
        headers: {
          'Cache-Control': 'no-store',
        },
      });
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

