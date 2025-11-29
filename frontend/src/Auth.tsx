import React, { useState, useEffect } from 'react';
import { useGetLoginUrlQuery } from './apiSlice';
import { RefreshCw } from 'lucide-react';

/**
 * Auth component that initiates the Upstox OAuth flow.
 * It fetches the login URL from the backend and opens a popup window.
 * The popup will post a message "auth_success" back to the opener when the
 * user completes authentication, allowing the main UI to refetch status.
 */
const Auth: React.FC = () => {
    const { data: loginResponse, isLoading, error, refetch } = useGetLoginUrlQuery();
    const [isAuthenticating, setIsAuthenticating] = useState(false);
    const [retryCount, setRetryCount] = useState(0);

    const loginUrl = loginResponse?.login_url;

    // Retry fetching login URL if there was an error
    useEffect(() => {
        if (error && retryCount < 3) {
            const timer = setTimeout(() => {
                refetch();
                setRetryCount(prev => prev + 1);
            }, 2000);
            return () => clearTimeout(timer);
        }
    }, [error, refetch, retryCount]);

    const handleConnect = () => {
        if (!loginUrl) return;
        
        setIsAuthenticating(true);
        console.log('🔐 Opening Upstox authentication popup...');
        
        // Open a small popup window for the OAuth flow
        const width = 500;
        const height = 600;
        const left = window.screenX + (window.innerWidth - width) / 2;
        const top = window.screenY + (window.innerHeight - height) / 2;
        const popup = window.open(
            loginUrl,
            'UpstoxAuth',
            `width=${width},height=${height},left=${left},top=${top}`,
        );
        
        // Monitor popup closure
        if (popup) {
            const checkPopup = setInterval(() => {
                if (popup.closed) {
                    clearInterval(checkPopup);
                    console.log('📝 Auth popup closed');
                    setIsAuthenticating(false);
                }
            }, 500);
        } else {
            console.warn('⚠️ Popup blocked! Please allow popups for this site.');
            setIsAuthenticating(false);
        }
    };

    const handleRetry = () => {
        setRetryCount(0);
        refetch();
    };

    if (isLoading) return <div className="text-gray-400 text-sm">Loading authentication link...</div>;
    if (error) return (
        <div className="flex flex-col gap-2">
            <div className="text-red-500 text-sm">Failed to load login URL.</div>
            <button
                onClick={handleRetry}
                className="px-3 py-2 bg-red-600 hover:bg-red-500 rounded text-white text-sm"
            >
                Retry
            </button>
        </div>
    );

    return (
        <button
            onClick={handleConnect}
            disabled={isAuthenticating || !loginUrl}
            className="w-full flex items-center justify-center gap-2 px-6 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:from-gray-500 disabled:to-gray-600 rounded-xl font-bold transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-blue-900/20 disabled:shadow-none"
        >
            <RefreshCw size={20} className={`text-white ${isAuthenticating ? 'animate-spin' : ''}`} /> 
            {isAuthenticating ? 'Authenticating...' : 'Connect Upstox'}
        </button>
    );
};

export default Auth;
