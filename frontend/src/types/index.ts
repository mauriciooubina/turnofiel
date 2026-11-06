export interface QueueMetrics {
  utilization: number;
  p0: number;
  Lq: number;
  Wq_hours: number;
  Wq_minutes: number;
  L: number;
  W_hours: number;
  W_minutes: number;
  stable: boolean;
}

export interface ShopQueueData {
  shop_id: string;
  lambda_rate: number;
  mu_rate: number;
  servers: number;
  metrics: QueueMetrics;
  active_barbers?: string[] | null;
  inactive_barbers?: string[] | null;
}

export interface Appointment {
  id: number;
  barber_id: number;
  barber_name: string;
  date: string;
  start_time: string;
  end_time: string;
  service_name: string;
  service_price: number;
  service_duration: number;
  client_hashed: string;
  is_self_booked: number;
  target: number | null;
  ausentismo_risk: 'ALTO' | 'MEDIO' | 'BAJO' | string;
  color_code: string;
  diagnostic?: string;
}

export interface PreventiveActionRequest {
  appointment_id: number;
  shop_id: 'hellfish' | 'hooligans';
  action_type: 'whatsapp' | 'confirm';
  message?: string | null;
}

export interface PreventiveActionResponse {
  id: number;
  appointment_id: number;
  shop_id: string;
  action_type: string;
  message?: string | null;
  created_at: string;
}
