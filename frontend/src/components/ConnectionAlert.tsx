import React from 'react';
import { WifiOff, X } from 'lucide-react';

interface ConnectionAlertProps {
  visible: boolean;
  snapshotDate: string;
  onClose: () => void;
}

export const ConnectionAlert: React.FC<ConnectionAlertProps> = ({
  visible,
  snapshotDate,
  onClose
}) => {
  if (!visible) return null;

  const parts = snapshotDate ? snapshotDate.split('-') : [];
  const formattedDate = parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : snapshotDate;

  return (
    <div
      role="alert"
      style={{
        position: 'fixed',
        bottom: '24px',
        left: '24px',
        background: '#fffbeb',
        border: '1px solid var(--warning-border)',
        color: 'var(--text-primary)',
        zIndex: 9998,
        maxWidth: '380px',
        borderRadius: '10px',
        padding: '14px 16px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        fontSize: '0.88rem',
        lineHeight: 1.4
      }}
    >
      <WifiOff size={20} style={{ color: 'var(--warning)', flexShrink: 0, marginTop: '2px' }} />
      <div style={{ flexGrow: 1 }}>
        <div style={{ fontWeight: 700, marginBottom: '2px' }}>
          Sin conexión
        </div>
        <div>
          No hay conexión con el backend. Se muestran datos locales de respaldo (agenda del {formattedDate}); el riesgo de turnos nuevos no se puede calcular.
        </div>
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label="Cerrar aviso"
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
          color: 'var(--text-secondary)',
          display: 'flex',
          alignItems: 'center',
          flexShrink: 0,
          marginLeft: '4px'
        }}
      >
        <X size={16} />
      </button>
    </div>
  );
};
