// TypeScript interfaces for instructor_list.svelte
export interface Instructor {
  neon_id: string | null;
  name: string;
  email: string;
  clearances: string[];
  volunteer_bio?: string;
  volunteer_picture?: string;
}

export interface SearchResult {
  neon_id: string;
  name: string;
  email: string;
}

export interface ToastMessage {
  color: 'success' | 'warning' | 'danger' | 'info';
  msg: string;
  title: string;
}

export type SortType = 'clearances_desc' | 'clearances_asc' | 'name';

export interface InstructorListData {
  instructors: Instructor[];
  education_lead: boolean;
}

export interface InstructorCapability {
  name: string;
  email: string;
  neon_id: string | null;
  active: boolean;
}

export interface ClassTemplate {
  name: string;
  approved: boolean;
  schedulable: boolean;
  "clearances earned": string[];
  "age requirement": string;
  capacity: number;
  supply_cost: number;
  price: number;
  hours: number;
  period: string;
  "name (from area)": string;
  "image link": string;
}

export interface AdminData {
  capabilities: InstructorCapability[];
  classes: ClassTemplate[];
}

export interface InstructorListWithCapabilities {
  instructors: Instructor[];
  education_lead: boolean;
  capabilities?: InstructorCapability[];
}
