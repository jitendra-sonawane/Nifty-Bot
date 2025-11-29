# Token Validation - Quick Reference

## What Changed?

The backend now **automatically validates** your Upstox access token and tells the frontend whether it's valid or expired.

## Before vs After

### Before ❌
- Token expires → API returns `401 UDAPI100050`
- Error: `Invalid token used to access API`
- User gets cryptic error message
- Bot stops working unexpectedly

### After ✅
- Token expires → Dashboard shows authentication screen
- Message: "Access token expired X hours ago. Please re-authenticate."
- One-click "Connect Upstox" button
- Seamless re-authentication flow

## How to Use

### 1. **Check Token Status Manually**
```bash
python3 backend/check_token.py
```

Output shows:
- ✅ **TOKEN VALID** - Valid for Xh Ym more
- ❌ **TOKEN EXPIRED** - Expired X seconds ago

### 2. **Get Token Status via API**
```bash
curl http://localhost:8000/auth/status
```

Response:
```json
{
  "authenticated": true,
  "token_status": {
    "is_valid": true,
    "expires_at": 1764480000,
    "remaining_seconds": 285120,
    "error_message": null
  }
}
```

### 3. **Dashboard Behavior**

**When Token is Valid:**
- ✅ Normal dashboard displayed
- If expires in < 1 hour: Yellow warning badge `⚠️ Token expires in Xm`

**When Token is Expired:**
- ❌ Full-screen authentication card
- Red key icon
- Error message explaining the issue
- "Connect Upstox" button
- Click to re-authenticate

## Re-authenticate When Token Expires

1. **Option A: Dashboard Button (Easiest)**
   - Dashboard shows "Connect Upstox" button
   - Click it
   - Complete Upstox login in popup
   - Token auto-saved to `.env`
   - Dashboard auto-refreshes

2. **Option B: Manual Token Generation**
   - Visit https://upstox.com/developer/apps
   - Generate new access token
   - Copy token
   - Click "Connect Upstox" in dashboard
   - Or manually update `.env` with new token

3. **Option C: Environment Variable**
   ```bash
   # Update .env
   UPSTOX_ACCESS_TOKEN=<new_token_here>
   
   # Restart backend
   python3 backend/server.py
   ```

## Token Status Meanings

| Status | Meaning | Action |
|--------|---------|--------|
| ✅ Valid, 10h+ remaining | Token is fresh | No action needed |
| ⚠️ Valid, < 1h remaining | Token expiring soon | Click warning badge to re-auth |
| ❌ Expired | Token is invalid | Click "Connect Upstox" to re-auth |
| ❌ Invalid format | Token is corrupted | Generate new token from Upstox |
| ❌ No token found | Token not set in .env | Click "Connect Upstox" to auth |

## API Endpoints

### Check Authentication Status
```
GET /auth/status

Returns:
{
  "authenticated": boolean,
  "token_status": {
    "is_valid": boolean,
    "expires_at": unix_timestamp,
    "remaining_seconds": integer,
    "error_message": string or null
  }
}
```

### Get Full Status (with auth info)
```
GET /status

Returns: Complete bot status including auth field
{
  "is_running": boolean,
  "current_price": float,
  ...
  "auth": {
    "authenticated": boolean,
    "token_status": {...}
  }
}
```

## Troubleshooting

### Q: Token keeps expiring quickly
**A:** Upstox tokens expire after 24 hours. This is normal. Set a reminder to re-authenticate daily before market hours close.

### Q: "Connect Upstox" button not working
**A:** 
- Check browser console for errors
- Ensure backend is running at `http://localhost:8000`
- Try manual token from https://upstox.com/developer/apps

### Q: Token valid but API still returns 401
**A:** 
- Token might be revoked on Upstox side
- Generate new token from Upstox dashboard
- Ensure you copied the full token (no extra spaces)
- Restart backend after updating token

### Q: How long do tokens last?
**A:** Upstox access tokens last **24 hours** from generation time.

## Code Reference

### Backend: Check Token in Code
```python
from app.core.config import Config

# Get token status
status = Config.is_token_valid()

if status['is_valid']:
    print(f"✅ Token valid for {status['remaining_seconds'] // 3600}h more")
else:
    print(f"❌ {status['error_message']}")
```

### Frontend: Show Auth Status
```tsx
const { data: status } = useGetStatusQuery();

if (!status?.auth?.authenticated) {
    // Show Auth component
    return <Auth />;
}

// Show dashboard
```

## Files That Handle Token Validation

1. **Backend:**
   - `backend/app/core/config.py` - `Config.is_token_valid()`
   - `backend/server.py` - `/auth/status` and `/status` endpoints
   - `backend/check_token.py` - CLI token checker

2. **Frontend:**
   - `frontend/src/Dashboard.tsx` - Auth guard and warning banner
   - `frontend/src/Auth.tsx` - "Connect Upstox" button component

## What's Next?

The system now:
1. ✅ Checks token validity before errors occur
2. ✅ Shows clear messages to users
3. ✅ Provides one-click re-authentication
4. ✅ Saves new tokens persistently
5. ✅ Warns about expiring tokens

When token is invalid, you'll no longer see cryptic 401 errors. Instead, the dashboard will guide you through re-authentication!
