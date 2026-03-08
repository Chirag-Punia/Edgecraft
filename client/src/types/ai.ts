export interface ReportData {
  columns: string[];
  rows: (string | number | boolean | null)[][];
  report_type: string;
  time_range: string;
}

export interface ChartSeries {
  name: string;
  data_key: string;
  color?: string;
}

export interface ChartData {
  chart_type: "line" | "bar" | "pie" | "stacked_bar" | "grouped_bar";
  title: string;
  x_key: string;
  series: ChartSeries[];
  x_label?: string;
  y_label?: string;
  currency_axis?: boolean;
}

export interface WebSource {
  title: string;
  url: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  report_data: ReportData | null;
  chart_data: ChartData | null;
  web_sources: WebSource[];
  created_at: string;
}

export interface ChatSession {
  id: number;
  title: string | null;
  language: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatResponse {
  session_id: number;
  message_id: number | null;
  content: string;
  report_data: ReportData | null;
  chart_data: ChartData | null;
  web_sources: WebSource[];
  suggested_questions: string[];
  language: string;
}
