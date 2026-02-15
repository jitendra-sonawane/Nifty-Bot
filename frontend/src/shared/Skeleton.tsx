import React from 'react';

interface SkeletonProps {
    className?: string;
    lines?: number;
}

const Skeleton: React.FC<SkeletonProps> = ({ className = '', lines = 1 }) => {
    return (
        <div className={`space-y-2 ${className}`}>
            {Array.from({ length: lines }).map((_, i) => (
                <div
                    key={i}
                    className="h-3 rounded animate-shimmer"
                    style={{ width: i === lines - 1 && lines > 1 ? '70%' : '100%' }}
                />
            ))}
        </div>
    );
};

export default Skeleton;
