import type { ShopQueueData, Appointment } from '@/types';
import fallbackCalendar from './fallbackCalendar.json';

export const FALLBACK_QUEUES: ShopQueueData[] = [
  {
    shop_id: "hellfish",
    lambda_rate: 1.5372,
    mu_rate: 1.6369,
    servers: 3,
    metrics: {
      utilization: 0.3130,
      p0: 0.3875,
      Lq: 0.0355,
      Wq_hours: 0.0231,
      Wq_minutes: 1.3845,
      L: 0.9745,
      W_hours: 0.6340,
      W_minutes: 38.0390,
      stable: true
    },
    active_barbers: ["Facundo (Yayu)", "Martin", "Mauro"],
    inactive_barbers: ["Alan", "Mauro"]
  },
  {
    shop_id: "hooligans",
    lambda_rate: 0.9605,
    mu_rate: 1.8458,
    servers: 2,
    metrics: {
      utilization: 0.2602,
      p0: 0.5871,
      Lq: 0.0378,
      Wq_hours: 0.0393,
      Wq_minutes: 2.3606,
      L: 0.5582,
      W_hours: 0.5811,
      W_minutes: 34.8673,
      stable: true
    },
    active_barbers: ["Sebastian Fraga", "Valentino"],
    inactive_barbers: ["Valen"]
  }
];

// Snapshot real de GET /api/calendar (2026-11-06) para las fechas por defecto de cada comercio.
export const FALLBACK_CALENDAR = fallbackCalendar as Record<'hellfish' | 'hooligans', { date: string; appointments: Appointment[] }>;

