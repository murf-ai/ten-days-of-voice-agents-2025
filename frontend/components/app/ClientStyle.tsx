import { useState, useEffect } from 'react';
import React from 'react';

// Assumes 'styles' is being passed down or imported globally
// If styles is a variable available in your layout scope, you need to adjust
// how you pass it to this component. For simplicity, let's assume `styles` 
// is passed as a prop.

interface ClientStyleProps {
    styles: string | null | undefined;
}

export function ClientStyle({ styles }: ClientStyleProps) {
    // Only render on the client side after hydration
    const [isClient, setIsClient] = useState(false);

    useEffect(() => {
        setIsClient(true);
    }, []);

    if (!isClient || !styles) {
        return null;
    }

    return <style dangerouslySetInnerHTML={{ __html: styles }} />;
}