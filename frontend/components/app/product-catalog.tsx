'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  currency: string;
  category: string;
  color?: string;
  size?: string;
}

interface ProductCatalogProps {
  className?: string;
}

export function ProductCatalog({ className }: ProductCatalogProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const response = await fetch('/api/products');
        if (!response.ok) {
          throw new Error('Failed to fetch products');
        }
        const data = await response.json();
        setProducts(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching products:', err);
        setError('Failed to load products');
      } finally {
        setLoading(false);
      }
    };

    fetchProducts();
  }, []);

  if (loading) {
    return (
      <div className={cn('p-4', className)}>
        <h2 className="text-lg font-semibold mb-4">Product Catalog</h2>
        <p className="text-sm text-muted-foreground">Loading products...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('p-4', className)}>
        <h2 className="text-lg font-semibold mb-4">Product Catalog</h2>
        <p className="text-sm text-destructive">{error}</p>
      </div>
    );
  }

  return (
    <div className={cn('p-4 md:p-6', className)}>
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Product Catalog</h2>
        <p className="text-sm text-muted-foreground">
          Browse our collection. Say "Add [product name] to cart" to shop!
        </p>
      </div>

      {products.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground">No products available</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.map((product) => (
            <div
              key={product.id}
              className="bg-card border border-border rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <div className="mb-2">
                <h3 className="font-semibold text-lg mb-1">{product.name}</h3>
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {product.description}
                </p>
              </div>

              <div className="flex flex-wrap gap-2 mb-3">
                <span className="text-xs bg-muted px-2 py-1 rounded capitalize">
                  {product.category}
                </span>
                {product.color && (
                  <span className="text-xs bg-muted px-2 py-1 rounded capitalize">
                    {product.color}
                  </span>
                )}
                {product.size && (
                  <span className="text-xs bg-muted px-2 py-1 rounded uppercase">
                    Size: {product.size}
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between">
                <span className="text-lg font-bold">
                  ₹{product.price.toLocaleString()} {product.currency}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

