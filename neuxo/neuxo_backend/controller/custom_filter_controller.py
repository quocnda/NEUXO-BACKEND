"""
Custom Filter Controller - Business Logic Layer
Handles custom filter related business logic
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.forms.models import model_to_dict
from django.utils import timezone

from neuxo_backend.models import CustomFilter


def get_custom_filters(user_id: int) -> List[Dict]:
    """Get all custom filters for a user"""
    filters = (
        CustomFilter.objects.filter(user_id=user_id)
        .values("id", "filter_name", "filter")
        .order_by("-filter_name")
    )
    return list(filters)


def create_custom_filter(
    user_id: int, filter_name: str, filter_data: Dict
) -> Optional[Dict]:
    """Create a new custom filter"""
    # Check if filter name already exists
    existing = CustomFilter.objects.filter(
        user_id=user_id, filter_name=filter_name
    ).exists()
    if existing:
        return None

    # Clean filter data - remove None values
    cleaned_filter = {k: v for k, v in filter_data.items() if v is not None}

    new_filter = CustomFilter.objects.create(
        user_id=user_id, filter_name=filter_name, filter=cleaned_filter
    )

    return {
        "id": str(new_filter.id),
        "filter_name": new_filter.filter_name,
        "filter": new_filter.filter,
    }


def update_custom_filter(
    filter_id: str, user_id: int, filter_name: str = None, filter_data: Dict = None
) -> Optional[Dict]:
    """Update an existing custom filter"""
    existing = CustomFilter.objects.filter(id=filter_id).values(
        "id", "filter_name", "user__id"
    ).first()

    if not existing:
        return {"error": "Filter not found"}

    if existing["user__id"] != user_id:
        return {"error": "No permission to update this filter"}

    # Build update data
    update_data = {"updated_at": timezone.now()}

    if filter_name:
        update_data["filter_name"] = filter_name

    if filter_data is not None:
        # Clean filter data
        cleaned_filter = {k: v for k, v in filter_data.items() if v is not None}
        update_data["filter"] = cleaned_filter

    CustomFilter.objects.filter(id=filter_id).update(**update_data)

    return {"success": True}


def save_custom_filter(
    user_id: int,
    filter_id: str = None,
    filter_name: str = None,
    filter_data: Dict = None,
) -> Dict:
    """Create or update a custom filter"""
    if filter_id:
        # Update existing filter
        return update_custom_filter(
            filter_id=filter_id,
            user_id=user_id,
            filter_name=filter_name,
            filter_data=filter_data,
        )
    else:
        # Create new filter
        if not filter_name:
            return {"error": "filter_name is required"}

        result = create_custom_filter(
            user_id=user_id,
            filter_name=filter_name,
            filter_data=filter_data or {},
        )

        if result is None:
            return {"error": "Filter name already exists"}

        return {"success": True, "data": result}


def delete_custom_filter(filter_id: str, user_id: int) -> Dict:
    """Delete a custom filter"""
    existing = CustomFilter.objects.filter(id=filter_id).values("id", "user__id").first()

    if not existing:
        return {"error": "Filter not found"}

    if existing["user__id"] != user_id:
        return {"error": "No permission to delete this filter"}

    CustomFilter.objects.filter(id=filter_id).delete()
    return {"success": True}
