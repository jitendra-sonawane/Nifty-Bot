# Authentication Flow - Quick Reference

## What Was Fixed

✅ **After successful Upstox authorization, the system now:**
1. Receives the auth code on the backend
2. Generates and saves the access token
3. Signals the frontend popup with `postMessage('auth_success', '*')`
4. Popup automatically closes
5. Dashboard receives the signal and refetches authentication status
6. System detects the new token and automatically loads the dashboard
7. All trading features become immediately available

## The Flow (Visual)

```
┌─────────────────────────────────────────────────────────────────┐
│ Dashboard showing "Authentication Required"                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
User clicks "Connect Upstox" button
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Popup Window Opens - Upstox Login                               │
│ URL: https://api.upstox.com/v2/login/authorization/dialog...   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
User completes Upstox authentication
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Upstox Redirects To: http://localhost:8000/auth/callback?code=X │
│ Backend receives authorization code                              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
Backend generates access token from code
                            ↓
Token saved to .env and all components updated
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Popup Window Now Shows Success Page                             │
│ "✅ Authentication Successful! Redirecting to dashboard..."    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
JavaScript in popup sends: window.opener.postMessage('auth_success', '*')
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Main Dashboard Window Receives Message                           │
│ Calls refetch() to get new status with authenticated = true      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
Popup closes automatically after 1.5 seconds
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Dashboard Now Shows Trading Interface                           │
│ "authenticated" = true, all features available                  │
└─────────────────────────────────────────────────────────────────┘
```

## Browser Console Output

When you authorize successfully, you should see these logs:

```
🔐 Opening Upstox authentication popup...
[Popup opens and user authenticates]
✅✅✅ Auth success message received!
📡 Token has been saved on server, now fetching status...
🔄 Refetching status (2nd attempt)...
🔄 Refetching status (3rd attempt)...
📝 Auth popup closed
[Dashboard loads automatically]
```

## Key Changes Made

### Backend (server.py)
- `/auth/callback` now returns HTML page with postMessage signal
- Popup displays success/error UI with proper styling
- Automatic popup closure after 1.5 seconds

### Frontend (Auth.tsx)
- Enhanced logging for debugging
- Better popup error handling

### Frontend (Dashboard.tsx)
- Improved auth_success message handler with multiple refetch attempts
- Better authentication required screen with instructions
- Enhanced console logging

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Still showing "Auth Required" after clicking connect | Check network tab - verify `/status` returns `auth.authenticated = true` |
| Popup blocked | Allow popups in browser settings for localhost:8000 |
| Auth code not working | Clear browser cache and try again, or restart backend |
| Token not saving | Check `.env` file permissions and disk space |
| Popup closes but no signal | Check browser console for errors, verify popup window.opener is set |

## Testing the Fix

1. **Clear cache** - Open DevTools → Application → Storage → Clear All
2. **Open Dashboard** - Navigate to http://localhost:3000
3. **Authenticate** - Click "Connect Upstox"
4. **Monitor Console** - Keep DevTools open to see logs
5. **Complete Auth** - Finish Upstox login
6. **Verify** - Should see dashboard load without "Auth Required" message

## Token Lifecycle

- **Generated**: When you complete Upstox authorization
- **Saved**: Immediately persisted to `.env` file
- **Propagated**: Updated in all backend components within 100ms
- **Used**: All API calls use the new token
- **Expiry**: Upstox tokens typically expire in 24 hours
- **Status**: Checked on every `/status` API call, warning displayed if < 1 hour remaining
