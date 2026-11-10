import React from 'react';
import { RefreshCw, Download, Calendar as CalendarIcon, BarChart2, WifiOff, ShieldCheck } from 'lucide-react';
import logoImg from '@/assets/logo.jpg';

interface HeaderProps {
  shopId: 'hellfish' | 'hooligans';
  setShopId: (shop: 'hellfish' | 'hooligans') => void;
  date: string;
  setDate: (date: string) => void;
  isFallbackMode: boolean;
  onRefresh: () => void;
  onExport: () => void;
  activeTab: 'agenda' | 'queues' | 'privacy';
  setActiveTab: (tab: 'agenda' | 'queues' | 'privacy') => void;
  username: string | null;
  canSwitchShop: boolean;
  isLocalDemo: boolean;
  onLogout: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  shopId,
  setShopId,
  date,
  setDate,
  isFallbackMode,
  onRefresh,
  onExport,
  activeTab,
  setActiveTab,
  username,
  canSwitchShop,
  isLocalDemo,
  onLogout,
}) => {
  return (
    <header className="app-navbar-unified fade-in">
      {/* 1. Left: Brand Identity (Logo Rectangular) */}
      <div className="navbar-brand">
        <img src={logoImg} alt="TurnoFiel" className="navbar-logo-img" />
        {isFallbackMode && (
          <span
            className="navbar-status-badge fallback"
            title="Sin conexión con el backend: datos locales de respaldo"
          >
            <WifiOff size={11} /> Sin conexión
          </span>
        )}
      </div>

      {/* 2. Center: Segmented Navigation Switcher */}
      <nav className="navbar-tabs-segmented">
        <button
          className={`nav-seg-tab ${activeTab === 'agenda' ? 'active' : ''}`}
          onClick={() => setActiveTab('agenda')}
        >
          <CalendarIcon size={15} />
          <span>Agenda diaria</span>
        </button>
        <button
          className={`nav-seg-tab ${activeTab === 'queues' ? 'active' : ''}`}
          onClick={() => setActiveTab('queues')}
        >
          <BarChart2 size={15} />
          <span>Análisis de Colas M/M/s</span>
        </button>
        <button
          className={`nav-seg-tab ${activeTab === 'privacy' ? 'active' : ''}`}
          onClick={() => setActiveTab('privacy')}
        >
          <ShieldCheck size={15} />
          <span>Privacidad</span>
        </button>
      </nav>

      {/* 3. Right: Contextual Controls (Shop Switcher + Date Picker + Refresh + User & Logout) */}
      <div className="navbar-controls">
        {/* Shop Switcher */}
        <div className="navbar-control-capsule">
          {canSwitchShop ? (
            <select
              className="navbar-select-input"
              value={shopId}
              onChange={(e) => setShopId(e.target.value as 'hellfish' | 'hooligans')}
            >
              <option value="hellfish">Hellfish Barbershop</option>
              <option value="hooligans">Barbería Hooligans</option>
            </select>
          ) : (
            <span className="navbar-static-shop-name">
              {shopId === 'hellfish' ? 'Hellfish Barbershop' : 'Barbería Hooligans'}
            </span>
          )}
        </div>

        {/* Date Picker & Refresh Button */}
        <div className="navbar-control-capsule">
          <input
            type="date"
            className="navbar-date-input"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <button
            onClick={onRefresh}
            className="navbar-refresh-btn"
            title="Recargar datos"
          >
            <RefreshCw size={13} />
          </button>
          <button
            type="button"
            onClick={onExport}
            disabled={isFallbackMode || isLocalDemo}
            className="navbar-export-btn"
            title={
              isFallbackMode || isLocalDemo
                ? 'La exportación requiere conexión con el backend'
                : 'Exportar CSV'
            }
            aria-label="Exportar CSV"
          >
            <Download size={13} />
            <span className="navbar-btn-label">Exportar CSV</span>
          </button>
        </div>

        {/* User Session Info & Logout */}
        <div className="navbar-user-capsule">
          <span className="navbar-username-label">
            {isLocalDemo ? 'Sin conexión' : (username ?? '')}
          </span>
          <button
            type="button"
            onClick={onLogout}
            className="navbar-logout-btn"
            title={isLocalDemo ? 'Salir de la demo' : 'Cerrar sesión'}
          >
            {isLocalDemo ? 'Salir de la demo' : 'Cerrar sesión'}
          </button>
        </div>
      </div>
    </header>
  );
};
