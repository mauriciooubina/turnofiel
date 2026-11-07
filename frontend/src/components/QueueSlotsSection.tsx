import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import type { ShopQueueData } from '@/types';
import { formatNumber, formatPercent } from '@/utils';

interface QueueSlotsSectionProps {
  queueMetrics: ShopQueueData;
  walkIns: Record<number, number>;
  onAddWalkIn: (hour: number) => void;
  onRemoveWalkIn: (hour: number) => void;
  onResetWalkIns: () => void;
  isRecalculating: boolean;
  isFallbackMode: boolean;
}

export const QueueSlotsSection: React.FC<QueueSlotsSectionProps> = ({
  queueMetrics,
  walkIns,
  onAddWalkIn,
  onRemoveWalkIn,
  onResetWalkIns,
  isRecalculating,
  isFallbackMode,
}) => {
  const { slots, date, mu_rate, servers } = queueMetrics;
  const isLocalFallback = isFallbackMode || !slots || slots.length === 0;

  const hasAnyWalkIn =
    Object.values(walkIns).some((v) => v > 0) ||
    Boolean(slots && slots.some((s) => s.walk_ins > 0));

  return (
    <div className="column-card" style={{ marginTop: '4px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Colas por franja horaria con walk-ins
          </h3>
          {date && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem', marginTop: '2px' }}>
              Fecha: {date}
            </p>
          )}
        </div>

        {!isLocalFallback && (
          <button
            type="button"
            className="queue-reset-btn"
            onClick={onResetWalkIns}
            disabled={isRecalculating || !hasAnyWalkIn}
          >
            <RotateCcw size={14} />
            Reiniciar walk-ins
          </button>
        )}
      </div>

      {isLocalFallback ? (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', padding: '12px 0' }}>
          Las colas por franja y la carga de walk-ins necesitan la API en vivo (no disponibles en Modalidad Local Demo).
        </div>
      ) : (
        <>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.86rem', lineHeight: 1.5, margin: '2px 0 8px 0' }}>
            λ de cada franja = asistencia esperada de los turnos agendados, Σ(1 − p) con p la probabilidad de ausentismo del modelo, más los walk-ins cargados. Se usan μ = {formatNumber(mu_rate, 3)} servicios/hora y s = {servers} prestadores del comercio. Los walk-ins no se guardan: se pierden al recargar o cambiar de día. ρ ≥ 1 indica que la franja no tiene capacidad libre para walk-ins; los turnos agendados se atienden en su horario.
          </p>

          <div style={{ overflowX: 'auto' }}>
            <table className="queue-slots-table">
              <thead>
                <tr>
                  <th>Franja</th>
                  <th style={{ textAlign: 'center' }}>Turnos agendados</th>
                  <th style={{ textAlign: 'right' }}>Asistencia esperada</th>
                  <th style={{ textAlign: 'center' }}>Walk-ins</th>
                  <th style={{ textAlign: 'right' }}>λ (clientes/h)</th>
                  <th style={{ textAlign: 'right' }}>ρ</th>
                  <th style={{ textAlign: 'right' }}>Wq (minutos)</th>
                  <th style={{ textAlign: 'center' }}>Estado</th>
                </tr>
              </thead>
              <tbody>
                {slots.map((slot) => {
                  const rhoColor =
                    slot.metrics.utilization > 0.8
                      ? 'var(--danger)'
                      : slot.metrics.utilization > 0.5
                      ? 'var(--warning)'
                      : 'var(--success)';

                  const hourFormatted = `${String(slot.hour).padStart(2, '0')}:00`;

                  return (
                    <tr key={slot.hour}>
                      <td style={{ fontWeight: 600 }}>{slot.label}</td>
                      <td style={{ textAlign: 'center' }}>{slot.scheduled}</td>
                      <td style={{ textAlign: 'right' }}>{formatNumber(slot.expected_attendance, 2)}</td>
                      <td style={{ textAlign: 'center' }}>
                        <div className="walk-in-controls">
                          <button
                            type="button"
                            className="walk-in-btn"
                            aria-label={`Quitar walk-in de las ${hourFormatted}`}
                            disabled={isRecalculating || slot.walk_ins <= 0}
                            onClick={() => onRemoveWalkIn(slot.hour)}
                          >
                            −
                          </button>
                          <span style={{ minWidth: '20px', textAlign: 'center', fontWeight: 600 }}>
                            {slot.walk_ins}
                          </span>
                          <button
                            type="button"
                            className="walk-in-btn walk-in-btn-add"
                            aria-label={`Agregar walk-in a las ${hourFormatted}`}
                            disabled={isRecalculating || slot.walk_ins >= 20}
                            onClick={() => onAddWalkIn(slot.hour)}
                          >
                            + walk-in
                          </button>
                        </div>
                      </td>
                      <td style={{ textAlign: 'right' }}>{formatNumber(slot.lambda_rate, 2)}</td>
                      <td style={{ textAlign: 'right', color: rhoColor, fontWeight: 700 }}>
                        {formatPercent(slot.metrics.utilization, 1)}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {slot.metrics.stable ? formatNumber(slot.metrics.Wq_minutes ?? 0, 1) : 'No aplica'}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        {slot.metrics.stable ? (
                          <span style={{ color: 'var(--success)', fontWeight: 600 }}>Estable</span>
                        ) : (
                          <span
                            style={{
                              color: 'var(--danger)',
                              fontWeight: 600,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <AlertTriangle size={15} />
                            Saturada
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};
