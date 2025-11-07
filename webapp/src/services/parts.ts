import { useQuery } from "@tanstack/react-query";
import axios from "axios";

export interface Part {
  id: number;
  name: string;
  sku: string;
  qty: number;
  min_qty: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const useParts = () =>
  useQuery({
    queryKey: ["parts"],
    queryFn: async () => {
      const response = await axios.get<PaginatedResponse<Part>>("/api/parts", {
        params: { page: 1, page_size: 50 }
      });
      return response.data;
    }
  });
