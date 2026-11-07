from typing import List, Optional
from pydantic import BaseModel

class QueueMetricsResponse(BaseModel):
    utilization: float
    p0: float
    Lq: Optional[float] = None
    Wq_hours: Optional[float] = None
    Wq_minutes: Optional[float] = None
    L: Optional[float] = None
    W_hours: Optional[float] = None
    W_minutes: Optional[float] = None
    stable: bool

class SlotQueueData(BaseModel):
    hour: int                    # 10..19 (hora de inicio de la franja)
    label: str                   # "10:00–11:00" (guion largo U+2013)
    scheduled: int               # turnos agendados que empiezan en esa hora
    expected_attendance: float   # Σ(1 − p) de esos turnos
    walk_ins: int
    lambda_rate: float           # expected_attendance + walk_ins (clientes/hora)
    metrics: QueueMetricsResponse

class ShopQueueData(BaseModel):
    shop_id: str
    lambda_rate: float
    mu_rate: float
    servers: int
    metrics: QueueMetricsResponse
    active_barbers: Optional[List[str]] = None
    inactive_barbers: Optional[List[str]] = None
    date: Optional[str] = None
    slots: Optional[List[SlotQueueData]] = None

