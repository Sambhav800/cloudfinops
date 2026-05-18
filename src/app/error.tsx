'use client';

import { useEffect } from 'react';

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        // Log the error to an error reporting service
        console.error('Global Error caught:', error);
    }, [error]);

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white p-4">
            <div className="max-w-md text-center space-y-6">
                <h2 className="text-3xl font-bold text-red-500">Something went wrong!</h2>
                <p className="text-gray-300">
                    We encountered an unexpected error. Check the console (F12) for details if you are debugging.
                </p>
                <div className="bg-gray-900 p-4 rounded-md border border-gray-800 text-left overflow-auto max-h-40">
                    <p className="text-xs font-mono text-red-400 break-words">
                        {error.message || "Unknown error occurred"}
                    </p>
                </div>
                <div className="flex justify-center gap-4">
                    <button
                        onClick={
                            // Attempt to recover by trying to re-render the segment
                            () => reset()
                        }
                        className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors"
                    >
                        Try again
                    </button>
                    <button
                        onClick={() => window.location.href = '/'}
                        className="px-6 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg font-medium transition-colors"
                    >
                        Go Home
                    </button>
                </div>
            </div>
        </div>
    );
}
