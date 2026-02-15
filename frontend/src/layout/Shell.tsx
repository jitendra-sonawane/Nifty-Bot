import React from 'react';

interface ShellProps {
    topbar: React.ReactNode;
    marketBar?: React.ReactNode;
    children: React.ReactNode;
}

const Shell: React.FC<ShellProps> = ({ topbar, marketBar, children }) => {
    return (
        <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] flex flex-col">
            {/* Sticky Header (Topbar + optional MarketOverviewBar) */}
            <header className="sticky top-0 z-40 bg-[var(--bg-primary)]/95 backdrop-blur-md border-b border-[var(--border-subtle)]">
                {topbar}
                {marketBar}
            </header>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto">
                <div className="max-w-[var(--max-content)] mx-auto p-3 lg:p-4">
                    {children}
                </div>
            </main>
        </div>
    );
};

export default Shell;
