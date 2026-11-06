# Frontend — Dashboard TurnoFiel

Dashboard web en React 19 + TypeScript + Vite que muestra la agenda del día con semaforización de riesgo de ausentismo y las métricas de teoría de colas $M/M/s$ por comercio.

## Comandos

```bash
npm install       # instalar dependencias
npm run dev       # servidor de desarrollo en http://localhost:5173
npm run build     # chequeo de tipos (tsc -b) + build de producción
npm run lint      # linter (oxlint)
npm run preview   # previsualizar el build
```

## Configuración

La URL del backend se toma de la variable `VITE_API_URL`. Si no está definida, se usa `http://localhost:8000`.

## Estructura

- `src/App.tsx`: componente principal, navegación por pestañas y modo fallback.
- `src/components/`: agenda (`AgendaTimeline`), alertas de ausentismo, métricas de colas, modal de simulación de turnos y notificaciones.
- `src/data/fallbackData.ts`: datos estáticos usados cuando el backend no responde.
- `src/types/`: tipos TypeScript de los contratos de la API.
