export const pad2 = n => n.toString().padStart(2, '0');
export const rnd = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
export const rndFloat = (min, max, dp = 1) => (Math.random() * (max - min) + min).toFixed(dp);
export const pick = arr => arr[Math.floor(Math.random() * arr.length)];
export const fmtTime = d => d.toLocaleTimeString('en-GB', { hour12: false });
export const fmtDate = d => `${d.getDate()} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()]} ${d.getFullYear()} ${fmtTime(d)}`;
export const commas = n => n.toLocaleString('en-US');

export const supervisors = [
  { email: 'amina.east@djezzy.dz',      zone: 'Zone East' },
  { email: 'karim.benaissa@djezzy.dz',  zone: 'Zone East' },
  { email: 'yasmine.hamdi@djezzy.dz',   zone: 'Zone East' },
  { email: 'ahmed.saidi@djezzy.dz',     zone: 'Zone East' },
  { email: 'malik.center@djezzy.dz',    zone: 'Zone Center' },
  { email: 'nadia.bouzid@djezzy.dz',    zone: 'Zone Center' },
  { email: 'farid.center@djezzy.dz',    zone: 'Zone Center' },
  { email: 'lamia.hadjar@djezzy.dz',    zone: 'Zone Center' },
  { email: 'sofiane.west@djezzy.dz',    zone: 'Zone West' },
  { email: 'wassim.belkacem@djezzy.dz', zone: 'Zone West' },
  { email: 'imane.cherif@djezzy.dz',    zone: 'Zone West' },
  { email: 'rachid.benmoussa@djezzy.dz',zone: 'Zone West' },
  { email: 'bilal.south@djezzy.dz',     zone: 'South Region' },
  { email: 'meriem.dahmani@djezzy.dz',  zone: 'South Region' },
  { email: 'tarek.messaoudi@djezzy.dz', zone: 'South Region' }
];

export const suspiciousSenders = [
  { email: 'gmail.contact92@gmail.com', zone: 'Zone East' },
  { email: 'no-reply@promo-deals.biz',  zone: 'Zone West' },
  { email: 'unknown.user@webmail.dz',   zone: 'Zone Center' }
];

export const REQUEST_TYPES = {
  LOCKED:    { key: 'Locked Account',      icon: '🔒', endpoint: '/v1/pos/unlock',      conf: [82, 99], dur: [900, 2200] },
  RESET:     { key: 'Password Reset',      icon: '🔑', endpoint: '/v1/pass/reset',       conf: [80, 98], dur: [700, 1900] },
  VPN:       { key: 'VPN Creation',        icon: '🌐', endpoint: '/v1/vpn/create',        conf: [78, 97], dur: [1400, 2600] },
  OTP:       { key: 'OTP Update',          icon: '📱', endpoint: '/v1/otp/update',        conf: [75, 96], dur: [900, 2100] },
  REACT:     { key: 'Account Reactivation',icon: '♻️', endpoint: '/v1/pos/reactivate',   conf: [80, 97], dur: [1100, 2400] },
  NEWPOS:    { key: 'New POS Account',     icon: '🏬', endpoint: '/v1/pos/create',        conf: [70, 94], dur: [1600, 3200] },
  IRRELEVANT:{ key: 'Irrelevant',          icon: '🗑️', endpoint: null,                   conf: [88, 99], dur: [150, 420] }
};

export const pdvCode = () => String(rnd(10000000, 99999999));
export const msisdn = () => `0${rnd(5,7)}${rnd(10,99)} ${rnd(10,99)} ${rnd(10,99)} ${rnd(10,99)}`;

const emailTemplatesFR = {
  LOCKED: pdv => `Bonjour support,\n\nLe compte associé au PDV ${pdv} est bloqué depuis ce matin. Merci de le débloquer rapidement, le point de vente ne peut plus encaisser.\n\nCordialement.`,
  RESET: pdv => `Bonjour,\n\nJe n'arrive plus à me connecter au PDV ${pdv}. Pouvez-vous réinitialiser le mot de passe ?\n\nMerci.`,
  VPN: pdv => `Bonjour équipe technique,\n\nMerci de créer un accès VPN pour le PDV ${pdv}, le technicien terrain en a besoin pour la maintenance.\n\nCordialement.`,
  OTP: (pdv, phone) => `Bonjour,\n\nMerci de mettre à jour le numéro OTP du PDV ${pdv} vers le ${phone}.\n\nCordialement.`,
  REACT: pdv => `Bonjour,\n\nLe compte du PDV ${pdv} a été suspendu par erreur, merci de le réactiver dès que possible.\n\nCordialement.`,
  NEWPOS: pdv => `Bonjour,\n\nNous ouvrons un nouveau point de vente, merci de créer le compte associé au PDV ${pdv}.\n\nCordialement.`,
  IRRELEVANT: () => pick([
    `Bonjour, pouvez-vous me confirmer les horaires d'ouverture du bureau régional ?`,
    `Newsletter Djezzy Business - offres du mois de juillet.`,
    `Rappel: réunion d'équipe SNOC prévue jeudi à 14h.`,
    `Bonjour, je cherche un stage en télécommunications, merci de me recontacter.`
  ])
};

let reqSeq = 20482;

function buildReasons(type, status, pdv, confidence, sender) {
  if (status === 'Escalated') {
    return [
      `confidence score ${confidence}% below the 85% automatic decision threshold`,
      `sender "${sender}" not found in the current zone whitelist`,
      `flagged for supervisor review before execution`
    ];
  }
  if (status === 'Rejected') {
    return [
      `no recognizable support intent detected in message body`,
      `classified as promotional / irrelevant content`,
      `dropped without API call, no reply sent`
    ];
  }
  switch (type) {
    case 'LOCKED': return [`detected "compte bloqué" keyword matching Locked Account intent`, `extracted valid 8-digit PDV code ${pdv}`, `sender authorized under zone whitelist`, `matched Locked Account template signature`];
    case 'RESET': return [`detected password reset intent keywords`, `extracted valid PDV code ${pdv}`, `sender authorized under zone whitelist`];
    case 'VPN': return [`detected VPN provisioning request`, `extracted PDV code ${pdv} and technician context`, `sender authorized under zone whitelist`];
    case 'OTP': return [`detected OTP update intent`, `extracted valid MSISDN and PDV code ${pdv}`, `sender authorized under zone whitelist`];
    case 'REACT': return [`detected reactivation request keywords`, `extracted PDV code ${pdv}`, `account suspension status confirmed via SNOC API`];
    case 'NEWPOS': return [`detected new POS account creation request`, `extracted PDV code ${pdv} and region metadata`, `sender authorized to request provisioning`];
    default: return [`no actionable intent detected`];
  }
}

export function generateRequest(atTime, forceType, forceStatus) {
  const weighted = ['LOCKED','LOCKED','LOCKED','RESET','RESET','OTP','VPN','REACT','NEWPOS','IRRELEVANT'];
  const typeKey = forceType || pick(weighted);
  const type = REQUEST_TYPES[typeKey];

  const useSuspicious = !forceStatus && Math.random() < 0.05;
  const senderObj = useSuspicious ? pick(suspiciousSenders) : pick(supervisors);
  const pdv = pdvCode();
  const phone = msisdn();

  let confidence = rnd(type.conf[0], type.conf[1]);
  let status = forceStatus;
  if (!status) {
    if (useSuspicious) { status = 'Escalated'; confidence = rnd(38, 68); }
    else if (typeKey === 'IRRELEVANT') { status = 'Rejected'; }
    else if (confidence < 85 && Math.random() < 0.55) { status = 'Escalated'; }
    else if (Math.random() < 0.03) { status = 'Processing'; }
    else { status = 'Success'; }
  }

  const durationMs = status === 'Processing' ? null : rnd(type.dur[0], type.dur[1]);
  const duration = durationMs === null ? '—' : (durationMs / 1000).toFixed(1) + 's';

  const emailBody = typeKey === 'OTP' ? emailTemplatesFR.OTP(pdv, phone) : emailTemplatesFR[typeKey](pdv);
  const cleanedBody = emailBody.replace(/\n+/g, ' ').replace(/Bonjour[^,]*,|Cordialement\.?|Merci\.?/gi, '').trim().slice(0, 140);

  let entityLabel = '—';
  if (typeKey === 'OTP') entityLabel = status === 'Escalated' && !phone ? 'Missing' : `MSISDN ${phone}`;
  else if (typeKey !== 'IRRELEVANT') entityLabel = status === 'Escalated' ? (Math.random() < 0.4 ? 'Missing PDV' : `PDV ${pdv}`) : `PDV ${pdv}`;

  const id = `SNOC-${typeKey.slice(0,4)}-${reqSeq--}`;

  const apiRequest = (status === 'Success' && type.endpoint) ? {
    endpoint: type.endpoint, method: 'POST',
    payload: typeKey === 'OTP' ? { msisdn: phone, pdv_code: pdv, supervisor: senderObj.email, zone: senderObj.zone } : { pdv_code: pdv, supervisor: senderObj.email, zone: senderObj.zone }
  } : null;

  const apiResponse = (status === 'Success' && type.endpoint) ? {
    status: 'success', pdv_code: pdv,
    message: {
      LOCKED: 'Account unlocked successfully', RESET: 'Password reset link generated', VPN: 'VPN access provisioned',
      OTP: 'OTP contact number updated', REACT: 'Account reactivated successfully', NEWPOS: 'POS account created successfully'
    }[typeKey]
  } : null;

  const replySubj = status === 'Rejected' ? null :
    status === 'Escalated' ? `Ticket Created — ${type.key} (Review Required)` :
    `Re: ${type.key} — PDV ${pdv} RESOLVED`;

  const replyBody = status === 'Rejected' ? null :
    status === 'Escalated' ? `Bonjour,\n\nVotre demande a été transmise à un superviseur pour vérification manuelle. Un agent vous recontactera sous peu.` :
    status === 'Processing' ? null :
    `Bonjour,\n\nVotre demande (${type.key}) a été traitée avec succès pour le PDV ${pdv}.\n\nCordialement,\nSNOC AI Agent`;

  return {
    id, typeKey, intent: type.key, icon: type.icon,
    sender: senderObj.email, zone: senderObj.zone,
    confidence, status, time: fmtTime(atTime), dateFull: fmtDate(atTime),
    duration, durationMs: durationMs || 0,
    pdv: typeKey === 'IRRELEVANT' ? null : pdv, phone: typeKey === 'OTP' ? phone : null,
    entity: entityLabel,
    action: status === 'Success' ? `API: ${type.key}` : status === 'Escalated' ? 'Human Review' : status === 'Processing' ? 'In Progress' : 'Drop',
    emailBody, cleanedBody,
    reasons: buildReasons(typeKey, status, pdv, status === 'Escalated' ? confidence : null, senderObj.email),
    apiRequest, apiResponse,
    replySubj, replyBody,
    lang: pick(['French (FR)', 'French (FR)', 'Algerian Arabic (DZ)', 'Franco-Arabic SMS'])
  };
}

export function seedRequestPool(count = 58) {
  const now = new Date();
  const pool = [];
  for (let i = 0; i < count; i++) {
    const t = new Date(now.getTime() - i * rnd(45, 420) * 1000);
    pool.push(generateRequest(t));
  }
  return pool;
}

export function seedAlerts() {
  const now = new Date();
  const mins = m => fmtTime(new Date(now.getTime() - m * 60000));
  return [
    { id: 'A1', severity: 'critical', message: 'VPN whitelist API latency above 900ms threshold', time: mins(6),  region: 'Zone West', status: 'Active' },
    { id: 'A2', severity: 'critical', message: 'Multiple Locked Account requests from Zone East (14 in 20 min)', time: mins(14), region: 'Zone East', status: 'Active' },
    { id: 'A3', severity: 'critical', message: 'Unauthorized sender attempted account unlock — sender not in whitelist', time: mins(22), region: 'Zone Center', status: 'Active' },
    { id: 'A4', severity: 'warning', message: 'OTP Update request missing PDV code — auto-escalated', time: mins(31), region: 'Zone West', status: 'Active' },
    { id: 'A5', severity: 'warning', message: 'Low-confidence classification requiring manual review (68%)', time: mins(38), region: 'South Region', status: 'Active' },
    { id: 'A6', severity: 'critical', message: 'SNOC API timeout on /v1/pos/unlock — retry succeeded after 2 attempts', time: mins(47), region: 'Zone East', status: 'Active' },
    { id: 'A7', severity: 'warning', message: 'High email traffic detected — 92 requests in the last hour', time: mins(55), region: 'All Zones', status: 'Active' },
    { id: 'A8', severity: 'info', message: 'POS 77481232 has 12 repeat incidents today', time: mins(70), region: 'Zone East', status: 'Resolved' },
    { id: 'A9', severity: 'info', message: 'Model pipeline v1.4.2 redeployed with no downtime', time: mins(95), region: 'All Zones', status: 'Resolved' }
  ];
}

export const initialHourly = [8, 12, 6, 4, 3, 5, 18, 45, 89, 120, 105, 78, 62, 55, 82, 95, 68, 42, 28, 18, 12, 8, 5, 3];
export const initialWeekly = [312, 348, 391, 356, 329, 168, 121];
