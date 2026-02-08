// TypeScript interfaces for techs_list.svelte
export interface Tech {
  neon_id: string | null;
  name: string;
  email: string;
  clearances: string[];
  shop_tech_shift: string[];
  shop_tech_first_day: string;
  shop_tech_last_day: string;
  area_lead: string;
  interest: string;
  expertise: string;
  volunteer_bio?: string;
  volunteer_picture?: string;
}

export interface DisplayTech extends Omit<Tech, 'shop_tech_shift'> {
  shop_tech_shift: string;
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

export interface TechListData {
  techs: Tech[];
  tech_lead: boolean;
}
