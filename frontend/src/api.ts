import axios from "axios";
import type {
  Equipment, Rental, Notification, ForecastItem, AnomalyItem, Summary, Customer, Site,
  MaintenanceItem, AgentResponse,
} from "./types";

const client = axios.create({ baseURL: "/api" });

export const login = (email: string, password: string) =>
  client.post("/auth/login", { email, password }).then((r) => r.data);

export const getEquipment = () =>
  client.get<Equipment[]>("/equipment").then((r) => r.data);

export const getCustomers = () =>
  client.get<Customer[]>("/customers").then((r) => r.data);

export const createCustomer = (payload: { name: string; company?: string; contact?: string }) =>
  client.post<Customer>("/customers", payload).then((r) => r.data);

export const getSites = () => client.get<Site[]>("/sites").then((r) => r.data);

export const getRentals = () =>
  client.get<Rental[]>("/rentals").then((r) => r.data);

export const createRental = (payload: {
  equipment_id: number;
  customer_id?: number;
  site_id?: number;
  rental_days?: number;
}) => client.post<Rental>("/rentals", payload).then((r) => r.data);

export const checkoutRental = (id: number) =>
  client.post<Rental>(`/rentals/${id}/checkout`).then((r) => r.data);

export const checkinRental = (id: number) =>
  client.post<Rental>(`/rentals/${id}/checkin`).then((r) => r.data);

export const getSummary = () =>
  client.get<Summary>("/dashboard/summary").then((r) => r.data);

export const getAlerts = () =>
  client.get<Notification[]>("/alerts").then((r) => r.data);

export const getForecast = () =>
  client.get<ForecastItem[]>("/forecast").then((r) => r.data);

export const getAnomalies = () =>
  client.get<AnomalyItem[]>("/anomalies").then((r) => r.data);

export const getMaintenance = () =>
  client.get<MaintenanceItem[]>("/maintenance").then((r) => r.data);

export const queryAgent = (message: string) =>
  client.post<AgentResponse>("/agent/query", { message }, { timeout: 60000 }).then((r) => r.data);
