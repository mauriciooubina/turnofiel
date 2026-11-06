import type { Appointment } from '@/types';

export const SHOP_DISPLAY_NAMES: Record<'hellfish' | 'hooligans', string> = {
  hellfish: 'Hellfish Barbershop',
  hooligans: 'Barbería Hooligans',
};

/**
 * Genera el mensaje personalizado de recordatorio para un turno.
 */
export function buildReminderMessage(app: Appointment, shopId: 'hellfish' | 'hooligans'): string {
  const shop = SHOP_DISPLAY_NAMES[shopId];
  const barbero = app.barber_name.replace(/\s*\(inactivo\)\s*/i, '').trim();
  const parts = app.date.split('-');
  const ddmm = parts.length === 3 ? `${parts[2]}/${parts[1]}` : app.date;
  const hhmm = app.start_time.substring(0, 5);

  return `¡Hola! Te escribimos de ${shop} para recordarte tu turno de ${app.service_name} el ${ddmm} a las ${hhmm} hs con ${barbero}. ¿Nos confirmás si venís? Si no podés, avisanos así liberamos el horario. ¡Gracias!`;
}

/**
 * Genera el enlace dinámico wa.me con el mensaje de WhatsApp.
 */
export function buildWhatsAppUrl(message: string): string {
  const rawNumber = import.meta.env.VITE_DEMO_WHATSAPP_NUMBER ?? '';
  const numero = rawNumber.replace(/\D/g, '');
  if (numero) {
    return `https://wa.me/${numero}?text=${encodeURIComponent(message)}`;
  }
  return `https://wa.me/?text=${encodeURIComponent(message)}`;
}
