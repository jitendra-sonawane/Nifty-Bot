import React, { type ReactNode, type ReactElement } from 'react';

interface ErrorBoundaryProps {
    children: ReactNode;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('ErrorBoundary caught an error:', error, errorInfo);
    }

    render(): ReactElement {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-gradient-to-br from-[#0b1020] via-[#101228] to-[#2b0f30] text-white p-4 flex items-center justify-center font-[var(--font-ui)]">
                    <div className="max-w-2xl w-full">
                        <div className="card rounded-xl bg-red-500/10 border border-red-500/30 shadow-lg p-6">
                            <h1 className="text-2xl font-bold text-red-400 mb-4">Something went wrong</h1>
                            <p className="text-red-300 mb-4">
                                An error occurred in the application. This might be due to a third-party library or extension.
                            </p>
                            <details className="bg-red-500/5 rounded p-4 mb-4">
                                <summary className="cursor-pointer text-red-300 font-semibold">Error Details</summary>
                                <pre className="text-xs text-red-200 mt-2 overflow-auto max-h-40">
                                    {this.state.error?.toString()}
                                </pre>
                            </details>
                            <button
                                onClick={() => window.location.reload()}
                                className="bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/50 text-cyan-400 px-4 py-2 rounded transition-colors"
                            >
                                Reload Page
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children as ReactElement;
    }
}

export default ErrorBoundary;
