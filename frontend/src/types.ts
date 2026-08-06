export interface Site {
  id: number;
  site_code: string;
  name?: string | null;
  lat?: number | null;
  lng?: number | null;
}

export interface Customer {
  id: number;
  name: string;
  company?: string | null;
  contact?: string | null;
}

export interface Tenure {
  designated_lat?: number | null;
  designated_lng?: number | null;
  assigned_since?: string | null;
  tenure_days?: number | null;
  last_compliant?: boolean | null;
  last_compliance_check?: string | null;
}

export interface Equipment {
  id: number;
  equipment_code: string;
  name?: string | null;
  type: string;
  status: string;
  assigned_customer_id?: number | null;
  assigned_site_id?: number | null;
  runtime_hours: number;
  fuel_usage: number;
  idle_hours: number;
  engine_health: number;
  gps_lat?: number | null;
  gps_lng?: number | null;
  last_operator_id?: string | null;
  return_date?: string | null;
  assigned_customer?: Customer | null;
  assigned_site?: Site | null;
  tenure?: Tenure | null;
}

export interface Rental {
  id: number;
  equipment_id: number;
  customer_id?: number | null;
  site_id?: number | null;
  status: string;
  qr_code?: string | null;
  check_in_date?: string | null;
  check_out_date?: string | null;
  return_date?: string | null;
  rental_days?: number | null;
}

export interface Notification {
  id: number;
  type: string;
  severity: string;
  message: string;
  equipment_id?: number | null;
  rental_id?: number | null;
  recommended_action?: string | null;
  created_at: string;
  read: boolean;
}

export interface ForecastItem {
  site_id: number;
  site_code: string | null;
  equipment_type: string;
  predicted_demand: number;
  rental_count: number;
  window: string;
}

export interface AnomalyItem {
  equipment_id: number;
  equipment_code: string;
  reason: string;
  severity: string;
  recommended_action: string;
}

export interface MaintenanceItem {
  equipment_id: number;
  equipment_code: string;
  risk_score: number;
  risk_level: "low" | "medium" | "high";
  reasons: string[];
  recommended_action: string;
}

export interface AgentResponse {
  response: string;
  agent_used: string;
  agent_key: string;
}

export interface Summary {
  total_equipment: number;
  rented_equipment: number;
  utilization_pct: number;
  total_rented_hours: number;
  total_idle_hours: number;
  idle_pct: number;
  downtime_equipment: number;
  downtime_pct: number;
  most_active_site: string | null;
  least_used_site: string | null;
  total_fuel_usage: number;
  usage_per_site: { site: string; hours: number }[];
  revenue_estimate: number;
}
