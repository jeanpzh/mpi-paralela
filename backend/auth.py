import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, jwk
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError
from functools import lru_cache
from typing import Dict, Any

from config import get_settings

settings = get_settings()
http_bearer = HTTPBearer()

@lru_cache(maxsize=1)
def get_jwks() -> Dict[str, Any]:
    """
    Retrieves the JSON Web Key Set (JWKS) from Clerk and caches it.
    The JWKS is used to verify the signature of JWTs.
    """
    jwks_url = f"{settings.clerk_jwt_issuer}/.well-known/jwks.json"
    try:
        with httpx.Client() as client:
            response = client.get(jwks_url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not fetch JWKS from Clerk: {e}",
        )


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> Dict[str, Any]:
    """
    A FastAPI dependency to validate the Clerk JWT and return the user claims.
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No credentials provided.",
        )
    
    token = creds.credentials
    jwks = get_jwks()
    
    try:
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
        if not rsa_key:
            raise HTTPException(status_code=401, detail="Unable to find matching key in JWKS")

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            issuer=settings.clerk_jwt_issuer,
            options={"verify_at_hash": False}, # Standard for Clerk
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTClaimsError as e:
        raise HTTPException(status_code=401, detail=f"Invalid claims: {e}")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Dependency to check for admin role
async def require_admin_user(user: Dict[str, Any] = Depends(get_current_user)):
    """
    A dependency that requires the user to have an 'admin' role in their metadata.
    """
    # Clerk stores custom claims under the 'claims' key in the session, 
    # which maps to 'session.public_metadata' in the Clerk dashboard.
    # The key 'metadata' within 'claims' is where it will be.
    claims = user.get("claims", {})
    metadata = claims.get("metadata", {})
    
    if metadata.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )
    return user 