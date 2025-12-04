import React from 'react';

interface ColumnProps {
    children: React.ReactNode;
    className?: string;
}

const Column: React.FC<ColumnProps> = ({ children, className = '' }) => {
    return (
        <div className={`flex flex-col gap-3 ${className}`}>
            {children}
        </div>
    );
};

export default Column;
