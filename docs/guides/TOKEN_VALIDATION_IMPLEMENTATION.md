# Token Validation Implementation

## Overview
Implemented automatic token validation on the backend and integrated it with the frontend dashboard to display "Connect to Upstox" button when the token is invalid or expired.

## Changes Made

### Backend (`backend/app/core/config.py`)

Added a new method `is_token_valid()` to the `Config` class:

```python
@classmethod
def is_token_valid(cls) -> dict:
    """Check if the access token is valid (not expired).
    Returns a dict with 'is_valid', 'expires_at', 'remaining_seconds', 'error_message'
    """
```

**Returns:**
- `is_valid` (bool): Whether the token is currently valid
- `expires_at` (float): Unix timestamp of token expiration
- `remaining_seconds` (int): Seconds until expiration (negative if expired)
- `error_message` (str): Human-readable error message or None if valid

**Features:**
- Decodes JWT token without verification (for diagnostics)
- Handles padding correctly
- Returns helpful error messages for:
  - Missing token: "No access token found. Please authenticate with Upstox."
  - Invalid format: "Invalid token format (not JWT)"
  - Expired token: "Access token expired X seconds ago. Please re-authenticate."
  - Parsing errors: "Error validating token: ..."

### Backend API (`backend/server.py`)

Added two new endpoints:

1. **GET `/auth/status`** - Check token validity
   ```json
   {
     "authenticated": false,
     "token_status": {
       "is_valid": false,
       "expires_at": 1764194400,
       "remaining_seconds": -22440,
       "error_message": "Access token expired 22440 seconds ago. Please re-authenticate."
     }
   }
   ```

2. **Updated GET `/status`** - Now includes auth information
   - Includes `auth` field with authentication status
   - Merges token validation into main status response

### Frontend (`frontend/src/Dashboard.tsx`)

**1. Added authentication state tracking:**
```tsx
const isAuthenticated = status?.auth?.authenticated;
const tokenStatus = status?.auth?.token_status;
```

**2. Added authentication guard:**
When `isAuthenticated` is false, the dashboard displays a centered card with:
- Red key icon
- "Authentication Required" heading
- Error message from token_status
- Hours-ago indicator if expired
- "Connect Upstox" button (Auth component)
- Help text

**3. Added token expiry warning banner:**
When token is about to expire (< 1 hour), shows yellow badge in header:
- `⚠️ Token expires in Xm`
- Only shows when token is valid but near expiration
- Disappears when fully expired (authentication required screen takes over)

## How It Works

### Token Validation Flow

1. **Backend check** (`Config.is_token_valid()`):
   ```
   Token exists? → Decode JWT → Check expiration → Return status
   ```

2. **API response** (`/status` endpoint):
   ```
   Bot status + Auth info (token validity, error message)
   ```

3. **Frontend logic**:
   ```
   Check status.auth.authenticated
     ├─ false → Show full-screen "Connect to Upstox" card
     └─ true  → Show normal dashboard
                └─ Remaining < 3600s → Show warning badge
   ```

## Testing

Test the implementation:

```bash
# Check current token status
cd backend
python3 backend/check_token.py

# Or use the API
curl http://localhost:8000/auth/status
```

Expected response when token is expired:
```json
{
  "authenticated": false,
  "token_status": {
    "is_valid": false,
    "expires_at": 1764194400,
    "remaining_seconds": -22445,
    "error_message": "Access token expired 22445 seconds ago. Please re-authenticate."
  }
}
```

## User Experience

### Expired Token Scenario
1. User accesses dashboard
2. Dashboard fetches `/status` 
3. Receives `authenticated: false`
4. Shows centered "Authentication Required" card
5. Displays error: "Access token expired X hours ago"
6. User clicks "Connect Upstox" button
7. OAuth flow initiates
8. After successful auth, token is saved
9. Dashboard automatically refetches and shows normal UI

### Token About to Expire
1. User is using dashboard normally
2. Token has < 1 hour remaining
3. Yellow warning badge appears in header: "⚠️ Token expires in Xm"
4. User can proactively re-authenticate before complete expiration
5. New token is saved, warning disappears

## Benefits

✅ **Proactive Validation**: Check token validity before making API calls
✅ **Clear User Feedback**: Error messages explain what went wrong
✅ **Early Warning**: Yellow badge alerts users before expiration
✅ **Seamless Recovery**: One-click "Connect to Upstox" button
✅ **No Breaking Errors**: 401 errors from Upstox are prevented
✅ **Persistent Tokens**: New token automatically saved to `.env`

## Files Modified

- `backend/app/core/config.py` - Added `is_token_valid()` method
- `backend/server.py` - Added `/auth/status` endpoint, updated `/status`
- `frontend/src/Dashboard.tsx` - Added auth state, guard, and warning banner
