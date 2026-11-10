import { useState, useEffect } from 'react';
import { Header } from '@/components/Header';
import { LoginScreen } from '@/components/LoginScreen';
import { QueueMetricsColumn } from '@/components/QueueMetricsColumn';
import { AgendaTimeline } from '@/components/AgendaTimeline';
import { AbsenteeismAlerts } from '@/components/AbsenteeismAlerts';
import { ToastNotification } from '@/components/ToastNotification';
import { ConnectionAlert } from '@/components/ConnectionAlert';
import { SimulateAppointmentModal } from '@/components/SimulateAppointmentModal';
import { ExportModal } from '@/components/ExportModal';
import { PrivacyPanel } from '@/components/PrivacyPanel';
import { FALLBACK_QUEUES, FALLBACK_CALENDAR } from '@/data/fallbackData';
import {
  apiFetch,
  clearSession,
  loadSession,
  AUTH_UNAUTHORIZED_EVENT,
  UnauthorizedError,
  buildReminderMessage,
  buildWhatsAppUrl,
} from '@/utils';
import type { AuthSession } from '@/utils';
import type { ShopQueueData, Appointment, PreventiveActionResponse } from '@/types';
import '@/styles/App.css';

const DEFAULT_DATES: Record<'hellfish' | 'hooligans', string> = {
  hooligans: '2026-01-21',
  hellfish: '2026-06-04',
};

function App() {
  const [session, setSession] = useState<AuthSession | null>(() => loadSession());
  const [isLocalDemo, setIsLocalDemo] = useState<boolean>(false);
  const [loginNotice, setLoginNotice] = useState<string | null>(null);

  const initialShop: 'hellfish' | 'hooligans' = session?.shop_id ?? 'hooligans';
  const [shopId, setShopId] = useState<'hellfish' | 'hooligans'>(initialShop);
  const [date, setDate] = useState<string>(DEFAULT_DATES[initialShop]);
  const [activeTab, setActiveTab] = useState<'agenda' | 'queues' | 'privacy'>('agenda');

  const [loading, setLoading] = useState<boolean>(true);
  const [isFallbackMode, setIsFallbackMode] = useState<boolean>(false);
  const [isConnectionAlertDismissed, setIsConnectionAlertDismissed] = useState<boolean>(false);
  const [isSimulateModalOpen, setIsSimulateModalOpen] = useState<boolean>(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState<boolean>(false);

  const [queueMetrics, setQueueMetrics] = useState<ShopQueueData | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);
  const [walkIns, setWalkIns] = useState<Record<number, number>>({});
  const [isRecalculating, setIsRecalculating] = useState<boolean>(false);

  const [triggeredActions, setTriggeredActions] = useState<Record<number, string>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const handleShopChange = (newShop: 'hellfish' | 'hooligans') => {
    setShopId(newShop);
    setDate(DEFAULT_DATES[newShop]);
  };

  useEffect(() => {
    const handleUnauthorized = () => {
      setSession(null);
      setTriggeredActions({});
      setLoginNotice('Tu sesión expiró. Volvé a iniciar sesión.');
      setAppointments([]);
      setQueueMetrics(null);
      setSelectedAppId(null);
      setWalkIns({});
      setLoading(true);
    };
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => {
      window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    };
  }, []);

  const handleLogin = (s: AuthSession) => {
    setSession(s);
    setLoginNotice(null);
    setIsLocalDemo(false);
    setTriggeredActions({});
    if (s.shop_id) {
      handleShopChange(s.shop_id);
    }
  };

  const handleEnterLocalDemo = () => {
    setIsLocalDemo(true);
    setLoginNotice(null);
  };

  const handleLogout = () => {
    clearSession();
    setSession(null);
    setIsLocalDemo(false);
    setTriggeredActions({});
    setLoginNotice(null);
    setAppointments([]);
    setQueueMetrics(null);
    setSelectedAppId(null);
    setWalkIns({});
    setLoading(true);
  };

  const fetchData = async (opts?: { silent?: boolean }) => {
    if (!session && !isLocalDemo) {
      return;
    }

    if (isLocalDemo) {
      setIsFallbackMode(true);
      const currentFallbackShop = FALLBACK_QUEUES.find((q) => q.shop_id === shopId);
      setQueueMetrics(currentFallbackShop || null);

      const snapshot = FALLBACK_CALENDAR[shopId];
      setAppointments(snapshot.date === date ? snapshot.appointments : []);
      setLoading(false);
      return;
    }

    if (!opts?.silent) setLoading(true);
    try {
      const queuesRes = await apiFetch(`${API_URL}/api/queues?shop_id=${shopId}&date=${date}`);
      if (!queuesRes.ok) throw new Error('API Queues error');
      const queuesData: ShopQueueData[] = await queuesRes.json();

      const currentShopQueue = queuesData.find((q) => q.shop_id === shopId);
      setQueueMetrics(currentShopQueue || null);

      const calendarRes = await apiFetch(`${API_URL}/api/calendar?shop_id=${shopId}&date=${date}`);
      if (!calendarRes.ok) throw new Error('API Calendar error');
      const calendarData = await calendarRes.json();

      setAppointments(calendarData.appointments || []);
      setIsFallbackMode(false);
      setIsConnectionAlertDismissed(false);

      try {
        const actionsRes = await apiFetch(`${API_URL}/api/actions?shop_id=${shopId}`);
        if (actionsRes.ok) {
          const actionsData: PreventiveActionResponse[] = await actionsRes.json();
          const fromServer: Record<number, string> = {};
          for (const act of actionsData) {
            if (act.action_type === 'confirm') {
              fromServer[act.appointment_id] = 'confirmed';
            } else if (act.action_type === 'whatsapp' && fromServer[act.appointment_id] !== 'confirmed') {
              fromServer[act.appointment_id] = 'whatsapp';
            }
          }
          setTriggeredActions((prev) => ({ ...prev, ...fromServer }));
        }
      } catch (actionsErr) {
        if (actionsErr instanceof UnauthorizedError) {
          return;
        }
        console.warn('Could not load actions history:', actionsErr);
      }
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        return;
      }
      console.warn('FastAPI backend is offline or unreachable. Loading fallback static mock data for demo...');
      setIsFallbackMode(true);

      const currentFallbackShop = FALLBACK_QUEUES.find((q) => q.shop_id === shopId);
      setQueueMetrics(currentFallbackShop || null);

      const snapshot = FALLBACK_CALENDAR[shopId];
      setAppointments(snapshot.date === date ? snapshot.appointments : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setWalkIns({});
    fetchData();
  }, [shopId, date, session, isLocalDemo]);

  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const recalculateQueues = async (next: Record<number, number>) => {
    setIsRecalculating(true);
    try {
      const activeHours = Object.keys(next)
        .map(Number)
        .filter((h) => (next[h] ?? 0) > 0)
        .sort((a, b) => a - b);

      let url = `${API_URL}/api/queues?shop_id=${shopId}&date=${date}`;
      if (activeHours.length > 0) {
        const rawWalkIns = activeHours.map((h) => `${h}:${next[h]}`).join(',');
        url += `&walk_ins=${encodeURIComponent(rawWalkIns)}`;
      }

      const res = await apiFetch(url);
      if (!res.ok) throw new Error('API Queues recalculate error');
      const data: ShopQueueData[] = await res.json();
      const currentShopQueue = data.find((q) => q.shop_id === shopId);
      setWalkIns(next);
      setQueueMetrics(currentShopQueue || null);
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        return;
      }
      triggerToast('No se pudo recalcular la cola. Probá de nuevo.');
    } finally {
      setIsRecalculating(false);
    }
  };

  const handleAddWalkIn = (hour: number) => {
    const current = walkIns[hour] || 0;
    if (current >= 20) return;
    const next = { ...walkIns, [hour]: current + 1 };
    recalculateQueues(next);
  };

  const handleRemoveWalkIn = (hour: number) => {
    const current = walkIns[hour] || 0;
    if (current <= 0) return;
    const next = { ...walkIns, [hour]: current - 1 };
    recalculateQueues(next);
  };

  const handleResetWalkIns = () => {
    recalculateQueues({});
  };

  const handleAction = async (app: Appointment, actionType: 'whatsapp' | 'confirm') => {
    if (actionType === 'whatsapp' && app.contact_blocked) {
      triggerToast('El cliente pidió no ser contactado: no se abrió WhatsApp.');
      return;
    }
    let message: string | null = null;
    const baseText =
      actionType === 'whatsapp'
        ? `Se abrió WhatsApp con el recordatorio del turno #${app.id}.`
        : `Turno #${app.id} confirmado.`;

    if (actionType === 'whatsapp') {
      message = buildReminderMessage(app, shopId);
      const url = buildWhatsAppUrl(message);
      window.open(url, '_blank', 'noopener,noreferrer');
      setTriggeredActions((prev) => ({ ...prev, [app.id]: 'whatsapp' }));
    } else {
      setTriggeredActions((prev) => ({ ...prev, [app.id]: 'confirmed' }));
    }

    if (isFallbackMode) {
      triggerToast(`${baseText} Sin conexión: la acción no se guardó.`);
      return;
    }

    try {
      const res = await apiFetch(`${API_URL}/api/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          appointment_id: app.id,
          shop_id: shopId,
          action_type: actionType,
          message,
        }),
      });

      if (res.ok) {
        triggerToast(`${baseText} Acción registrada.`);
      } else if (res.status === 409) {
        triggerToast('El cliente pidió no ser contactado: no se registró el recordatorio.');
      } else {
        triggerToast(`${baseText} No se pudo registrar la acción en el servidor.`);
      }
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        return;
      }
      triggerToast(`${baseText} No se pudo registrar la acción en el servidor.`);
    }
  };

  const handleAppointmentCreated = (newApp: Appointment) => {
    if (newApp.date && newApp.date !== date) {
      setDate(newApp.date);
    }
    setAppointments((prev) => {
      const filtered = prev.filter((a) => a.id !== newApp.id);
      const updated = [...filtered, newApp].sort((a, b) => a.start_time.localeCompare(b.start_time));
      return updated;
    });
    setSelectedAppId(newApp.id);
    setActiveTab('agenda');
    triggerToast('Turno agendado exitosamente.');
  };

  if (!session && !isLocalDemo) {
    return (
      <LoginScreen
        apiUrl={API_URL}
        onLogin={handleLogin}
        onEnterLocalDemo={handleEnterLocalDemo}
        notice={loginNotice}
      />
    );
  }

  return (
    <div className="app-container">
      {/* Fallback Connection Alert */}
      <ConnectionAlert
        visible={isFallbackMode && !isConnectionAlertDismissed}
        snapshotDate={FALLBACK_CALENDAR[shopId].date}
        onClose={() => setIsConnectionAlertDismissed(true)}
      />

      {/* Notification popup alert */}
      <ToastNotification message={toastMessage} />

      {/* Header controls & tabs section */}
      <Header
        shopId={shopId}
        setShopId={handleShopChange}
        date={date}
        setDate={setDate}
        isFallbackMode={isFallbackMode}
        onRefresh={() => fetchData()}
        onExport={() => setIsExportModalOpen(true)}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        username={session?.username ?? null}
        canSwitchShop={isLocalDemo || session?.role === 'admin'}
        isLocalDemo={isLocalDemo}
        onLogout={handleLogout}
      />

      {/* Live Demo Simulation Modal */}
      <SimulateAppointmentModal
        isOpen={isSimulateModalOpen}
        onClose={() => setIsSimulateModalOpen(false)}
        shopId={shopId}
        currentDate={date}
        onAppointmentCreated={handleAppointmentCreated}
      />

      {/* Operative Data Export Modal */}
      <ExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        shopId={shopId}
        date={date}
        onExported={() => triggerToast('Exportación descargada.')}
      />

      {loading ? (
        <div className="loading-container">
          <div className="spinner"></div>
          <span style={{ marginLeft: '12px' }}>Cargando datos del panel...</span>
        </div>
      ) : (
        <main>
          {activeTab === 'agenda' ? (
            /* TAB 1: Agenda & Alerts (2-Column Grid) */
            <div className="view-grid-agenda fade-in">
              <AgendaTimeline
                appointments={appointments}
                triggeredActions={triggeredActions}
                selectedAppId={selectedAppId}
                onSelectApp={(id) => setSelectedAppId((prev) => (prev === id ? null : id))}
                onOpenSimulateModal={() => setIsSimulateModalOpen(true)}
              />

              <AbsenteeismAlerts
                appointments={appointments}
                triggeredActions={triggeredActions}
                handleAction={handleAction}
                selectedAppId={selectedAppId}
              />
            </div>
          ) : activeTab === 'queues' ? (
            /* TAB 2: Queuing Theory Detailed Analytics View */
            <QueueMetricsColumn
              queueMetrics={queueMetrics}
              shopId={shopId}
              walkIns={walkIns}
              onAddWalkIn={handleAddWalkIn}
              onRemoveWalkIn={handleRemoveWalkIn}
              onResetWalkIns={handleResetWalkIns}
              isRecalculating={isRecalculating}
              isFallbackMode={isFallbackMode}
            />
          ) : (
            /* TAB 3: Privacy and ARCO Rights */
            <PrivacyPanel
              shopId={shopId}
              isFallbackMode={isFallbackMode}
              onPrivacyChanged={() => fetchData({ silent: true })}
            />
          )}
        </main>
      )}
    </div>
  );
}

export default App;
