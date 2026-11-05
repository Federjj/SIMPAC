import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { gzipSync } from "node:zlib";
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

// Deja un .gz al lado de cada .js/.css/.svg/.json/.html del build que pese 1 KB o más: nginx lo sirve
// tal cual (nginx.conf, gzip_static) sin comprimir en cada visita. Sin dependencias: zlib de Node.
// Es solo del build; en desarrollo (vite) no hace nada. En Vercel y Netlify (variables VERCEL y
// NETLIFY, que sus builds definen solas) no corre: esas plataformas comprimen por su cuenta y los
// .gz solo serían archivos de más en el despliegue.
const enPlataforma = Boolean(process.env.VERCEL || process.env.NETLIFY);

function precomprimir() {
  let salida = "dist";
  return {
    name: "simpac-precomprimir",
    apply: "build",
    configResolved(c) {
      salida = c.build.outDir;
    },
    closeBundle() {
      const archivos = [];
      const recorrer = (dir) => {
        for (const n of readdirSync(dir)) {
          const p = join(dir, n);
          if (statSync(p).isDirectory()) recorrer(p);
          else if (/\.(js|mjs|css|svg|json|html|webmanifest)$/.test(n)) archivos.push(p);
        }
      };
      recorrer(salida);
      for (const p of archivos) {
        const contenido = readFileSync(p);
        if (contenido.length < 1024) continue;
        writeFileSync(`${p}.gz`, gzipSync(contenido, { level: 9 }));
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), ...(enPlataforma ? [] : [precomprimir()])],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: { port: 5173, host: true },
  build: {
    rollupOptions: {
      output: {
        // vendors en chunks propios: un cambio en el código de SIMPAC solo invalida el chunk index
        // (~64 KB gz) y no los ~190 KB gz de React, Leaflet y supabase-js, que el navegador ya tiene.
        // Radix no se separa: con React en otro chunk queda una dependencia circular.
        manualChunks: {
          react: ["react", "react-dom"],
          leaflet: ["leaflet"],
          supabase: ["@supabase/supabase-js"],
        },
      },
    },
  },
});
