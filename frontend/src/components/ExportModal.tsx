import React, { useState, useEffect, useMemo } from 'react';
import { X, Download, FileText, AlertTriangle } from 'lucide-react';
import { apiFetch, UnauthorizedError } from '@/utils';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  shopId: 'hellfish' | 'hooligans';
  date: string;
  onExported: () => void;
}

function getRangeDays(fromStr: string, toStr: string): number {
  const [y1, m1, d1] = fromStr.split('-').map(Number);
  const [y2, m2, d2] = toStr.split('-').map(Number);
  const utc1 = Date.UTC(y1, m1 - 1, d1);
  const utc2 = Date.UTC(y2, m2 - 1, d2);
  return Math.round((utc2 - utc1) / (1000 * 60 * 60 * 24)) + 1;
}

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  shopId,
  date,
  onExported,
}) => {
  const [dateFrom, setDateFrom] = useState<string>(date);
  const [dateTo, setDateTo] = useState<string>(date);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setDateFrom(date);
      setDateTo(date);
      setErrorMsg(null);
    }
  }, [isOpen, date]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const validationError = useMemo(() => {
    if (!dateFrom || !dateTo) {
      return 'Completá las fechas de inicio y fin.';
    }
    if (dateTo < dateFrom) {
      return 'La fecha hasta no puede ser anterior a la fecha desde.';
    }
    const days = getRangeDays(dateFrom, dateTo);
    if (days > 31) {
      return 'El rango máximo de exportación es de 31 días.';
    }
    return null;
  }, [dateFrom, dateTo]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validationError) return;

    setIsDownloading(true);
    setErrorMsg(null);

    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    try {
      const res = await apiFetch(
        `${API_URL}/api/export?shop_id=${encodeURIComponent(shopId)}&date_from=${encodeURIComponent(
          dateFrom
        )}&date_to=${encodeURIComponent(dateTo)}`,
        {},
        30000
      );

      if (!res.ok) {
        let detail = 'No se pudo generar la exportación.';
        try {
          const data = await res.json();
          if (data && data.detail) {
            detail = data.detail;
          }
        } catch {
          // detalle por defecto
        }
        setErrorMsg(detail);
        return;
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `turnofiel_${shopId}_${dateFrom}_${dateTo}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      onExported();
      onClose();
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        return;
      }
      setErrorMsg('No se pudo generar la exportación.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-modal-title"
      >
        {/* Header */}
        <div className="modal-header">
          <h2 id="export-modal-title">
            <FileText size={20} color="#0f172a" />
            Exportar datos operativos
          </h2>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            title="Cerrar"
            aria-label="Cerrar"
          >
            <X size={20} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="modal-body">
          <p
            style={{
              fontSize: '0.86rem',
              color: 'var(--text-secondary)',
              lineHeight: 1.45,
              margin: '0 0 16px 0',
            }}
          >
            Descarga en CSV los turnos del comercio con su riesgo y la acción preventiva sugerida.
            Los clientes que pidieron la supresión de sus datos salen sin identificador.
          </p>

          <div className="modal-form-grid">
            <div className="form-field">
              <label htmlFor="export-date-from">Desde:</label>
              <input
                id="export-date-from"
                type="date"
                className="form-input"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>

            <div className="form-field">
              <label htmlFor="export-date-to">Hasta:</label>
              <input
                id="export-date-to"
                type="date"
                className="form-input"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
          </div>

          {validationError && (
            <div
              style={{
                fontSize: '0.82rem',
                color: 'var(--danger)',
                marginTop: '10px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <AlertTriangle size={14} />
              <span>{validationError}</span>
            </div>
          )}

          {errorMsg && (
            <div
              role="alert"
              style={{
                background: 'var(--danger-bg)',
                border: '1px solid var(--danger)',
                padding: '10px 12px',
                borderRadius: '8px',
                color: 'var(--danger)',
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                lineHeight: 1.4,
                marginTop: '12px',
              }}
            >
              <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Footer Buttons */}
          <div
            className="modal-footer"
            style={{ margin: '-24px', marginTop: '16px', padding: '16px 24px' }}
          >
            <button type="button" className="modal-cancel-btn" onClick={onClose}>
              Cancelar
            </button>
            <button
              type="submit"
              className="modal-submit-btn"
              disabled={isDownloading || !!validationError}
            >
              {isDownloading ? (
                <>
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                  Generando...
                </>
              ) : (
                <>
                  <Download size={16} />
                  Descargar CSV
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
