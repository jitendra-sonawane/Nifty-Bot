import React from 'react';

interface DashboardLayoutProps {
    children: React.ReactNode;
}

const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
    return (
        <div className="min-h-screen bg-gradient-to-br from-[#0b1020] via-[#101228] to-[#2b0f30] text-white p-2 font-[var(--font-ui)] relative overflow-x-hidden w-screen">
            <div className="w-full max-w-[1600px] mx-auto space-y-3">
                {children}
            </div>
        </div>
    );
};

export default DashboardLayout;
