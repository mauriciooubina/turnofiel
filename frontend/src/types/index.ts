export interface QueueMetrics {
  utilization: number;
  p0: number;
  Lq: number | null;
  Wq_hours: number | null;
  Wq_minutes: number | null;
  L: number | null;
  W_hours: number | null;
  W_minutes: number | null;
  stable: boolean;
}

export interface SlotQueueData {
  hour: number;
  label: string;
  scheduled: number;
  expected_attendance: number;
  walk_ins: number;
  lambda_rate: number;
  metrics: QueueMetrics;
}

export interface ShopQueueData {
  shop_id: string;
  lambda_rate: number;
  mu_rate: number;
  servers: number;
  metrics: QueueMetrics;
  active_barbers?: string[] | null;
  inactive_barbers?: string[] | null;
  date?: string | null;
  slots?: SlotQueueData[] | null;
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
  noshow_probability?: number | null;
  color_code: string;
  diagnostic?: string;
  contact_blocked?: boolean;
  client_erased?: boolean;
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

export interface PrivacyClientAppointment {
  id: number;
  date: string;
  start_time: string;
  service_name?: string | null;
  barber_name?: string | null;
  target?: number | null;
}

export interface PrivacyClientRecord {
  client_hashed: string;
  total_appointments: number;
  no_shows: number;
  do_not_contact: boolean;
  erased: boolean;
  erased_at?: string | null;
  appointments: PrivacyClientAppointment[];
}

export interface PrivacySearchResponse {
  shop_id: 'hellfish' | 'hooligans';
  query_type: 'phone' | 'client_hashed';
  clients: PrivacyClientRecord[];
}

export type PrivacyRequestType = 'do_not_contact' | 'allow_contact' | 'erasure';

export interface PrivacyStateResponse {
  client_hashed: string;
  do_not_contact: boolean;
  erased: boolean;
  erased_at?: string | null;
}
