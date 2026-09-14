// Cliente de Supabase para el frontend (lectura pública con la publishable key).
// Requiere: npm install @supabase/supabase-js
import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

if (!url || !key) {
  console.warn(
    "Faltan VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY. " +
      "Copia frontend/.env.example a frontend/.env"
  );
}

export const supabase = createClient(url, key);
