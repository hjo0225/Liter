from fastapi import APIRouter, Depends

from app.core.deps import get_current_user

router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user.get("sub"),
        "email": current_user.get("email"),
        "name": current_user.get("user_metadata", {}).get("name"),
    }
