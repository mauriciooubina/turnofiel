import React, { useState, useEffect } from 'react';
import { Search, ShieldAlert, ShieldCheck, AlertCircle, Trash2, UserX, UserCheck } from 'lucide-react';
import type { PrivacyClientRecord, PrivacyRequestType } from '@/types';
import { apiFetch, UnauthorizedError } from '@/utils';

interface PrivacyPanelProps {
  shopId: 'hellfish' | 'hooligans';
  isFallbackMode: boolean;
  onPrivacyChanged: () => void;
}

function formatDateDdMmYyyy(isoStr: string | null | undefined): string {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return isoStr;
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
}

export const PrivacyPanel: React.FC<PrivacyPanelProps> = ({
  shopId,
  isFallbackMode,
  onPrivacyChanged,
}) => {
  const [query, setQuery] = useState('');
  const [lastQuery, setLastQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [clients, setClients] = useState<PrivacyClientRecord[] | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [erasureConfirmTarget, setErasureConfirmTarget] = useState<string | null>(null);
  const [isActionSubmitting, setIsActionSubmitting] = useState(false);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    setQuery('');
    setLastQuery('');
    setClients(null);
    setErrorMsg(null);
    setErasureConfirmTarget(null);
  }, [shopId]);

  const executeSearch = async (searchQuery: string) => {
    const trimmed = searchQuery.trim();
    if (!trimmed) return;
    setIsSearching(true);
    setErrorMsg(null);
    setErasureConfirmTarget(null);

    try {
      const res = await apiFetch(`${API_URL}/api/privacy/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shop_id: shopId, query: trimmed }),
      });

      if (!res.ok) {
        let detail = 'No se pudo completar la operación. Intentá de nuevo.';
        try {
          const errData = await res.json();
          if (errData && errData.detail) {
            if (typeof errData.detail === 'string') detail = errData.detail;
          }
        } catch {
          // fallback
        }
        setErrorMsg(detail);
        setClients(null);
        return;
      }

      const data = await res.json();
      setLastQuery(trimmed);
      setClients(data.clients || []);
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) {
        return;
      }
      setErrorMsg('No se pudo completar la operación. Intentá de nuevo.');
      setClients(null);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(query);
  };

  const handlePrivacyAction = async (clientHashed: string, requestType: PrivacyRequestType) => {
    setIsActionSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await apiFetch(`${API_URL}/api/privacy/requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          shop_id: shopId,
          client_hashed: clientHashed,
          request_type: requestType,
        }),
      });

      if (!res.ok) {
        let detail = 'No se pudo completar la operación. Intentá de nuevo.';
        try {
          const errData = await res.json();
          if (errData && errData.detail) {
            if (typeof errData.detail === 'string') detail = errData.detail;
          }
        } catch {
          // fallback
        }
        setErrorMsg(detail);
        return;
      }

      setErasureConfirmTarget(null);
      await executeSearch(lastQuery);
      onPrivacyChanged();
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) {
        return;
      }
      setErrorMsg('No se pudo completar la operación. Intentá de nuevo.');
    } finally {
      setIsActionSubmitting(false);
    }
  };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px', width: '100%', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ background: 'var(--card-bg)', border: '1px solid var(--card-border)', borderRadius: '12px', padding: '24px', boxShadow: 'var(--card-shadow)' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ShieldCheck size={22} style={{ color: 'var(--secondary)' }} />
          Privacidad y derechos ARCO (Ley 25.326)
        </h2>
        {isFallbackMode ? (
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginTop: '12px' }}>
            La gestión de privacidad necesita el servidor: no está disponible en Modalidad Local Demo.
          </p>
        ) : (
          <>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: 1.5, marginBottom: '20px' }}>
              Gestioná los pedidos que los clientes le hacen al comercio. TurnoFiel solo guarda identificadores con hash: el teléfono que ingreses se convierte en hash en el servidor y no se guarda.
            </p>

            <form onSubmit={handleSearchSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label htmlFor="privacy-search-input" style={{ fontSize: '0.86rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                Teléfono del cliente o identificador (hash)
              </label>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <input
                  id="privacy-search-input"
                  type="text"
                  autoComplete="off"
                  inputMode="text"
                  className="login-input"
                  style={{ flex: '1 1 280px', minWidth: '220px' }}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ej: 1123456789 o hash de 16 caracteres"
                />
                <button
                  type="submit"
                  className="login-submit-btn"
                  style={{ width: 'auto', padding: '9px 24px', margin: 0, display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  disabled={!query.trim() || isSearching}
                >
                  <Search size={15} />
                  {isSearching ? 'Buscando...' : 'Buscar'}
                </button>
              </div>
            </form>

            {errorMsg && (
              <div
                role="alert"
                style={{
                  background: 'var(--danger-bg)',
                  border: '1px solid var(--danger)',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  color: 'var(--danger)',
                  fontSize: '0.88rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  marginTop: '16px',
                }}
              >
                <AlertCircle size={18} style={{ flexShrink: 0 }} />
                <span>{errorMsg}</span>
              </div>
            )}

            {clients !== null && clients.length === 0 && (
              <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.92rem', background: '#f8fafc', borderRadius: '8px', marginTop: '16px', border: '1px solid var(--card-border)' }}>
                No hay turnos de ese cliente en este comercio.
              </div>
            )}

            {clients !== null && clients.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '20px' }}>
                {clients.map((client) => {
                  const isConfirming = erasureConfirmTarget === client.client_hashed;
                  return (
                    <div
                      key={client.client_hashed}
                      style={{
                        background: 'var(--card-bg)',
                        border: '1px solid var(--card-border)',
                        borderRadius: '10px',
                        padding: '18px',
                        boxShadow: 'var(--card-shadow)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '14px',
                      }}
                    >
                      {/* Header of client card */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                            Cliente {client.client_hashed}
                          </span>
                          {/* Estado badge */}
                          {client.erased ? (
                            <span
                              style={{
                                background: 'var(--danger-bg)',
                                color: 'var(--danger)',
                                border: '1px solid var(--danger-border)',
                                fontSize: '0.74rem',
                                fontWeight: 600,
                                padding: '3px 8px',
                                borderRadius: '6px',
                              }}
                            >
                              Datos suprimidos el {formatDateDdMmYyyy(client.erased_at)}
                            </span>
                          ) : client.do_not_contact ? (
                            <span
                              style={{
                                background: 'var(--warning-bg)',
                                color: 'var(--warning)',
                                border: '1px solid var(--warning-border)',
                                fontSize: '0.74rem',
                                fontWeight: 600,
                                padding: '3px 8px',
                                borderRadius: '6px',
                              }}
                            >
                              No contactar
                            </span>
                          ) : (
                            <span
                              style={{
                                background: 'var(--success-bg)',
                                color: 'var(--success)',
                                border: '1px solid var(--success-border)',
                                fontSize: '0.74rem',
                                fontWeight: 600,
                                padding: '3px 8px',
                                borderRadius: '6px',
                              }}
                            >
                              Contacto permitido
                            </span>
                          )}
                        </div>

                        {!client.erased && !isConfirming && (
                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            <button
                              type="button"
                              className="action-trigger-btn secondary"
                              style={{ padding: '6px 12px', fontSize: '0.82rem' }}
                              disabled={isActionSubmitting}
                              onClick={() =>
                                handlePrivacyAction(
                                  client.client_hashed,
                                  client.do_not_contact ? 'allow_contact' : 'do_not_contact'
                                )
                              }
                            >
                              {client.do_not_contact ? (
                                <>
                                  <UserCheck size={14} />
                                  Permitir contacto
                                </>
                              ) : (
                                <>
                                  <UserX size={14} />
                                  No contactar
                                </>
                              )}
                            </button>
                            <button
                              type="button"
                              className="action-trigger-btn"
                              style={{
                                padding: '6px 12px',
                                fontSize: '0.82rem',
                                background: 'var(--danger-bg)',
                                color: 'var(--danger)',
                                borderColor: 'var(--danger-border)',
                              }}
                              disabled={isActionSubmitting}
                              onClick={() => setErasureConfirmTarget(client.client_hashed)}
                            >
                              <Trash2 size={14} />
                              Suprimir datos
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Confirmation box on erasure */}
                      {isConfirming && (
                        <div
                          style={{
                            background: 'var(--danger-bg)',
                            border: '1px solid var(--danger-border)',
                            borderRadius: '8px',
                            padding: '14px 16px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '12px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', color: 'var(--danger)', fontSize: '0.86rem', lineHeight: 1.45 }}>
                            <ShieldAlert size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                            <span>
                              Vas a suprimir los datos de este cliente (Art. 16). Sus turnos van a seguir contando para las estadísticas del comercio, sin ningún vínculo con la persona, y el modelo los va a evaluar sin su historial. No se puede deshacer desde la aplicación.
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                            <button
                              type="button"
                              className="action-trigger-btn secondary"
                              style={{ padding: '6px 14px', fontSize: '0.84rem' }}
                              disabled={isActionSubmitting}
                              onClick={() => setErasureConfirmTarget(null)}
                            >
                              Cancelar
                            </button>
                            <button
                              type="button"
                              className="action-trigger-btn"
                              style={{
                                padding: '6px 14px',
                                fontSize: '0.84rem',
                                background: 'var(--danger)',
                                color: '#ffffff',
                                border: 'none',
                              }}
                              disabled={isActionSubmitting}
                              onClick={() => handlePrivacyAction(client.client_hashed, 'erasure')}
                            >
                              {isActionSubmitting ? 'Suprimiendo...' : 'Confirmar supresión'}
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Client Stats & Appointments Table */}
                      {!client.erased && (
                        <>
                          <div style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                            {client.total_appointments} turnos · {client.no_shows} ausencias
                          </div>

                          <div style={{ width: '100%', overflowX: 'auto' }}>
                            <table className="queue-slots-table" style={{ marginTop: '4px' }}>
                              <thead>
                                <tr>
                                  <th>Fecha</th>
                                  <th>Hora</th>
                                  <th>Servicio</th>
                                  <th>Profesional</th>
                                  <th>Asistencia</th>
                                </tr>
                              </thead>
                              <tbody>
                                {client.appointments.map((apt) => (
                                  <tr key={apt.id}>
                                    <td>{apt.date}</td>
                                    <td>{apt.start_time}</td>
                                    <td>{apt.service_name ?? '—'}</td>
                                    <td>{apt.barber_name ?? '—'}</td>
                                    <td>
                                      {apt.target === 0
                                        ? 'Asistió'
                                        : apt.target === 1
                                        ? 'No asistió'
                                        : 'Sin dato'}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Bottom info section */}
            <div
              style={{
                marginTop: '28px',
                paddingTop: '16px',
                borderTop: '1px solid var(--card-border)',
                fontSize: '0.8rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
                display: 'flex',
                flexWrap: 'wrap',
                gap: '8px',
              }}
            >
              <span>Acceso: esta búsqueda muestra los turnos que TurnoFiel tiene del cliente.</span>
              <span>·</span>
              <span>Rectificación: los datos de contacto se corrigen en el sistema de reservas del comercio, de donde provienen.</span>
              <span>·</span>
              <span>Cancelación (supresión): botón "Suprimir datos".</span>
              <span>·</span>
              <span>Oposición: botón "No contactar".</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
