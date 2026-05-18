'use client';

import { useEffect } from 'react';

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        console.error('Root Global Error caught:', error);
    }, [error]);

    return (
        <html>
            <body className="bg-black text-white">
                <div className="flex flex-col items-center justify-center min-h-screen p-4">
                    <h2 className="text-3xl font-bold text-red-500 mb-4">Critical Error</h2>
                    <p className="mb-6 text-gray-300">The application failed to load completely.</p>

                    <div className="bg-gray-900 p-4 rounded-md border border-gray-800 text-left overflow-auto max-h-40 max-w-lg mb-6">
                        <p className="text-xs font-mono text-red-400 break-words">
                            {error.message || "Unknown critical error"}
                        </p>
                    </div>

                    <button
                        onClick={() => reset()}
                        className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors"
                    >
                        Try again
                    </button>
                </div>
            </body>
        </html>
    );
}
