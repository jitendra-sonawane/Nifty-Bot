import React, { useState, useEffect } from 'react';
import { useGetLoginUrlQuery } from '../../apiSlice';
import { RefreshCw } from 'lucide-react';

const Auth: React.FC = () => {
    const { data: loginResponse, isLoading, isFetching, error, refetch } = useGetLoginUrlQuery();
    const [isAuthenticating, setIsAuthenticating] = useState(false);
    const [retryCount, setRetryCount] = useState(0);

    const loginUrl = loginResponse?.login_url;

    useEffect(() => {
        if (error && retryCount < 3) {
            const timer = setTimeout(() => {
                refetch();
                setRetryCount((prev) => prev + 1);
            }, 2000);
            return () => clearTimeout(timer);
        }
    }, [error, refetch, retryCount]);

    const handleConnect = () => {
        if (!loginUrl) return;
        setIsAuthenticating(true);

        const width = 500;
        const height = 600;
        const left = window.screenX + (window.innerWidth - width) / 2;
        const top = window.screenY + (window.innerHeight - height) / 2;
        const popup = window.open(
            loginUrl,
            'UpstoxAuth',
            `width=${width},height=${height},left=${left},top=${top}`
        );

        if (popup) {
            const checkPopup = setInterval(() => {
                if (popup.closed) {
                    clearInterval(checkPopup);
                    setIsAuthenticating(false);
                }
            }, 500);
        } else {
            setIsAuthenticating(false);
        }
    };

    if (isLoading || isFetching)
        return <div className="text-[var(--text-muted)] text-sm text-center py-2">Loading…</div>;

    if (error)
        return (
            <button
                onClick={() => { setRetryCount(0); refetch(); }}
                className="w-full py-2.5 rounded-lg font-semibold text-sm text-white bg-[var(--color-loss)] hover:opacity-90 transition-opacity"
            >
                Retry Connection
            </button>
        );

    return (
        <button
            onClick={handleConnect}
            disabled={isAuthenticating || !loginUrl}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-bold text-sm text-white
        bg-gradient-to-r from-[var(--accent-blue)] to-[var(--accent-indigo)]
        hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
            <RefreshCw size={16} className={isAuthenticating ? 'animate-spin' : ''} />
            {isAuthenticating ? 'Authenticating…' : 'Connect Upstox'}
        </button>
    );
};

export default Auth;
