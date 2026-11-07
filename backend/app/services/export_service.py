"""
Servicio de exportación de datos operativos de agenda en formato CSV.
Cumple con Ley 25.326 suprimiendo identificadores de clientes que lo hayan solicitado.
"""

import csv
from datetime import date, datetime, timedelta
import io
from typing import Any, Dict, List

from fastapi import HTTPException

from app.config import DATA_SOURCE
from app.schemas.calendar import AppointmentResponse
from app.services.actions_service import list_actions
from app.services.calendar_service import get_calendar_data
from app.services.privacy_service import fetch_privacy_state

MAX_EXPORT_DAYS = 31

CSV_COLUMNS = [
    'fecha',
    'hora_inicio',
    'hora_fin',
    'turno_id',
    'profesional',
    'servicio',
    'precio_servicio',
    'duracion_min',
    'cliente_hash',
    'canal',
    'riesgo',
    'probabilidad_ausencia',
    'accion_sugerida',
    'contacto_bloqueado',
    'datos_suprimidos',
    'acciones_registradas',
    'asistencia_real',
]


class InvalidExportRange(ValueError):
    """Excepción lanzada cuando el rango de fechas para exportar es inválido."""
    pass


class ExportUnavailable(RuntimeError):
    """Excepción lanzada cuando el servicio de exportación no está disponible."""
    pass


def parse_export_range(date_from: str, date_to: str) -> tuple[date, date]:
    """Valida y parsea el rango de fechas YYYY-MM-DD para la exportación."""
    try:
        d_from = date.fromisoformat(date_from)
        d_to = date.fromisoformat(date_to)
    except (ValueError, TypeError) as exc:
        raise InvalidExportRange("Formato de fecha inválido. Utilice el formato YYYY-MM-DD.") from exc

    if d_to < d_from:
        raise InvalidExportRange("La fecha 'hasta' no puede ser anterior a la fecha 'desde'.")

    days_count = (d_to - d_from).days + 1
    if days_count > MAX_EXPORT_DAYS:
        raise InvalidExportRange("El rango máximo de exportación es de 31 días.")

    return d_from, d_to


def suggested_action(risk: str, contact_blocked: bool) -> str:
    """Devuelve la acción preventiva recomendada según el nivel de riesgo y estado de contacto."""
    if risk == "ALTO":
        if not contact_blocked:
            return "Recordatorio priorizado por WhatsApp o confirmación manual"
        return "Confirmación manual (cliente sin contacto por WhatsApp)"
    elif risk == "MEDIO":
        return "Monitoreo en la agenda"
    return "Sin intervención"


def format_actions(actions: List[Dict[str, Any]]) -> str:
    """Formatea la lista de acciones preventivas cronológicamente separadas por pleca."""
    if not actions:
        return ""

    def get_sort_key(act: Dict[str, Any]):
        dt = act.get("created_at")
        if isinstance(dt, datetime):
            return dt
        if isinstance(dt, str):
            try:
                return datetime.fromisoformat(dt)
            except Exception:
                pass
        return datetime.min

    sorted_actions = sorted(actions, key=get_sort_key)
    parts = []
    for act in sorted_actions:
        act_type = str(act.get("action_type", "")).lower()
        prefix = "WhatsApp" if act_type == "whatsapp" else "Confirmación"
        dt = act.get("created_at")
        if isinstance(dt, datetime):
            dt_str = dt.strftime("%Y-%m-%d %H:%M")
        elif isinstance(dt, str):
            try:
                dt_obj = datetime.fromisoformat(dt)
                dt_str = dt_obj.strftime("%Y-%m-%d %H:%M")
            except Exception:
                dt_str = dt[:16].replace("T", " ")
        else:
            dt_str = str(dt)
        parts.append(f"{prefix} {dt_str}")

    return " | ".join(parts)


def format_decimal(value: float | None, decimals: int) -> str:
    """Formatea un número decimal sustituyendo el punto por coma."""
    if value is None:
        return ""
    return f"{value:.{decimals}f}".replace('.', ',')


def safe_cell(value: Any) -> str:
    """Previene inyección de fórmulas CSV anteponiendo un apóstrofe si inicia con caracteres reservados."""
    text = str(value) if value is not None else ""
    if text and text[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{text}"
    return text


def appointment_to_row(
    appt: AppointmentResponse, actions_by_id: Dict[int, List[Dict[str, Any]]]
) -> Dict[str, str]:
    """Mapea un turno al diccionario de columnas para el archivo CSV de exportación."""
    canal = "autogestión" if appt.is_self_booked == 1 else "personal"
    contacto_bloqueado = "sí" if appt.contact_blocked else "no"
    datos_suprimidos = "sí" if appt.client_erased else "no"

    if appt.target == 0:
        asistencia = "asistió"
    elif appt.target == 1:
        asistencia = "no asistió"
    else:
        asistencia = ""

    appt_actions = actions_by_id.get(appt.id, [])

    return {
        'fecha': safe_cell(appt.date),
        'hora_inicio': safe_cell(appt.start_time),
        'hora_fin': safe_cell(appt.end_time),
        'turno_id': safe_cell(str(appt.id)),
        'profesional': safe_cell(appt.barber_name),
        'servicio': safe_cell(appt.service_name),
        'precio_servicio': safe_cell(format_decimal(appt.service_price, 2)),
        'duracion_min': safe_cell(str(appt.service_duration)),
        'cliente_hash': safe_cell(appt.client_hashed if appt.client_hashed is not None else ""),
        'canal': safe_cell(canal),
        'riesgo': safe_cell(appt.ausentismo_risk),
        'probabilidad_ausencia': safe_cell(format_decimal(appt.noshow_probability, 4)),
        'accion_sugerida': safe_cell(suggested_action(appt.ausentismo_risk, appt.contact_blocked)),
        'contacto_bloqueado': safe_cell(contacto_bloqueado),
        'datos_suprimidos': safe_cell(datos_suprimidos),
        'acciones_registradas': safe_cell(format_actions(appt_actions)),
        'asistencia_real': safe_cell(asistencia),
    }


def build_export_rows(shop_id: str, d_from: date, d_to: date) -> List[Dict[str, str]]:
    """Genera las filas de exportación consultando la agenda día por día con privacidad y acciones."""
    if DATA_SOURCE != "POSTGRES":
        raise ExportUnavailable("La exportación requiere la base de datos.")

    try:
        state = fetch_privacy_state(shop_id)
        actions = list_actions(shop_id)
    except Exception as exc:
        raise ExportUnavailable("La exportación requiere la base de datos.") from exc

    erased = {h for h, v in state.items() if v.get('erased')}
    blocked = {h for h, v in state.items() if v.get('erased') or v.get('do_not_contact')}

    actions_by_id: Dict[int, List[Dict[str, Any]]] = {}
    for act in actions:
        appt_id = act.get('appointment_id')
        if appt_id is not None:
            actions_by_id.setdefault(appt_id, []).append(act)

    rows: List[Dict[str, str]] = []
    curr = d_from
    while curr <= d_to:
        d_str = curr.isoformat()
        try:
            cal = get_calendar_data(shop_id=shop_id, date=d_str)
            for appt in cal.appointments:
                if appt.date == d_str:
                    if appt.client_hashed in erased:
                        appt = appt.model_copy(
                            update={'client_hashed': '', 'client_erased': True, 'contact_blocked': True}
                        )
                    elif appt.client_hashed in blocked:
                        appt = appt.model_copy(update={'contact_blocked': True})
                    row = appointment_to_row(appt, actions_by_id)
                    rows.append(row)
        except HTTPException as exc:
            if exc.status_code == 404:
                curr += timedelta(days=1)
                continue
            raise
        curr += timedelta(days=1)

    rows.sort(
        key=lambda r: (
            r['fecha'],
            r['hora_inicio'],
            int(r['turno_id'].lstrip("'")),
        )
    )
    return rows


def rows_to_csv(rows: List[Dict[str, str]]) -> str:
    """Convierte las filas a texto CSV delimitado por punto y coma con BOM UTF-8."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=CSV_COLUMNS,
        delimiter=';',
        lineterminator='\r\n',
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return '\ufeff' + output.getvalue()
