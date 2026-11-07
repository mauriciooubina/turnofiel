from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.config import SHOP_SALTS
from app.dependencies import ensure_shop_access, get_current_user
from app.schemas.auth import CurrentUser
from app.services.export_service import (
    ExportUnavailable,
    InvalidExportRange,
    build_export_rows,
    parse_export_range,
    rows_to_csv,
)

router = APIRouter(prefix="/api/export", tags=["Export"])


@router.get("", status_code=status.HTTP_200_OK)
def export_appointments_endpoint(
    shop_id: str = Query(...),
    date_from: str = Query(...),
    date_to: str = Query(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Descarga los turnos del rango seleccionado en formato CSV con riesgo y acciones preventivas."""
    ensure_shop_access(user, shop_id)

    shop = shop_id.lower()
    if shop not in SHOP_SALTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comercio desconocido.",
        )

    try:
        d_from, d_to = parse_export_range(date_from, date_to)
    except InvalidExportRange as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    try:
        rows = build_export_rows(shop, d_from, d_to)
    except ExportUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    csv_content = rows_to_csv(rows)
    filename = f"turnofiel_{shop}_{d_from.isoformat()}_{d_to.isoformat()}.csv"

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
