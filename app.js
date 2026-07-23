document.addEventListener('DOMContentLoaded', () => {

  /* ================================================================
     0. HELPERS
     ================================================================ */
  const pad2 = n => n.toString().padStart(2, '0');
  const rnd = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
  const rndFloat = (min, max, dp = 1) => (Math.random() * (max - min) + min).toFixed(dp);
  const pick = arr => arr[Math.floor(Math.random() * arr.length)];
  const fmtTime = d => d.toLocaleTimeString('en-GB', { hour12: false });
  const fmtDate = d => `${d.getDate()} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()]} ${d.getFullYear()} ${fmtTime(d)}`;
  const commas = n => n.toLocaleString('en-US');

  /* Interface language ------------------------------------------------ */
  const translationsFR = {
    'Home': 'Accueil', 'Emails': 'E-mails', 'Audit': 'Audit', 'Operations': 'Opérations',
    'Operation Analysis': 'Analyse opérationnelle', 'Business Analysis': 'Analyse métier', 'Parameters': 'Paramètres',
    'Refresh': 'Actualiser', 'Process Inbox': 'Traiter la boîte de réception', 'Pause Agent': "Mettre l’agent en pause",
    'Resume Agent': "Reprendre l’agent", 'Agent Active': 'Agent actif', 'Agent Paused': 'Agent en pause',
    'Welcome back to SNOC 👋': 'Bienvenue sur SNOC 👋', "Today's Snapshot": "Aperçu du jour",
    'What happened today?': "Que s’est-il passé aujourd’hui ?", 'Automatically Resolved': 'Résolues automatiquement',
    'Escalated': 'Escaladées', 'Rejected': 'Rejetées', 'Live Feed': 'Flux en direct', 'Quality Metrics': 'Indicateurs de qualité',
    'Live Email Activity Timeline': "Chronologie de l’activité des e-mails", 'Click any row to inspect AI decision lifecycle': "Cliquez sur une ligne pour examiner la décision de l’IA",
    'Success Rate': 'Taux de réussite', 'Failure Rate': "Taux d’échec", 'Avg Processing Time': 'Temps moyen de traitement',
    'Avg API Execution': "Exécution API moyenne", 'Low Confidence Predictions': 'Prédictions à faible confiance',
    'Missing Entities': 'Entités manquantes', 'Unauthorized Requests': 'Demandes non autorisées', 'Rejected Emails': 'E-mails rejetés',
    'Escalation Count': "Nombre d’escalades", 'Avg Confidence Score': 'Score de confiance moyen',
    'All Requests': 'Toutes les demandes', 'Locked Account': 'Compte bloqué', 'VPN Creation': 'Création VPN',
    'OTP Update': 'Mise à jour OTP', 'Password Reset': 'Réinitialisation du mot de passe',
    'Audit Log': "Journal d’audit", 'Current Queue': "File d’attente actuelle", 'Search': 'Rechercher',
    'Active Operational Warnings': 'Alertes opérationnelles actives', 'Email Text': "Texte de l’e-mail", 'Extracted Values': 'Valeurs extraites',
    'API Exchange': 'Échange API', 'Outgoing Response Preview': 'Aperçu de la réponse envoyée',
    'Service Provisioning': 'Création VPN', 'Account Access': 'Compte bloqué',
    'Require dual approval for VPN Creation': 'Exiger une double approbation pour la création VPN',
    'New VPN creation requests always route to a human, regardless of confidence score.': 'Les demandes de création VPN sont toujours transmises à un agent, quel que soit le score de confiance.',
    'What is happening with support emails?': 'Que se passe-t-il avec les e-mails de support ?'
  };
  const originalText = new WeakMap();
  let dashboardLanguage = localStorage.getItem('snoc-dashboard-language') || 'en';
  function localizeTextNode(node) {
    if (!originalText.has(node)) originalText.set(node, node.nodeValue);
    const original = originalText.get(node);
    const leading = original.match(/^\s*/)[0], trailing = original.match(/\s*$/)[0], key = original.trim();
    node.nodeValue = leading + (dashboardLanguage === 'fr' ? (translationsFR[key] || key) : key) + trailing;
  }
  function applyLanguage(root = document.body) {
    document.documentElement.lang = dashboardLanguage;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.parentElement || ['SCRIPT', 'STYLE'].includes(node.parentElement.tagName)) continue;
      if (node.nodeValue.trim()) localizeTextNode(node);
    }
    const search = document.getElementById('global-search');
    if (search) search.placeholder = dashboardLanguage === 'fr' ? 'Rechercher par PDV, expéditeur, e-mail, téléphone ou demande…' : 'Search by PDV, sender, email, phone or request...';
  }
  function setupLanguageSwitcher() {
    const select = document.getElementById('dashboard-language');
    if (!select) return;
    select.value = dashboardLanguage;
    select.addEventListener('change', () => { dashboardLanguage = select.value; localStorage.setItem('snoc-dashboard-language', dashboardLanguage); applyLanguage(); });
    new MutationObserver(mutations => {
      if (dashboardLanguage !== 'fr') return;
      mutations.forEach(m => m.addedNodes.forEach(n => {
        if (n.nodeType === Node.TEXT_NODE) localizeTextNode(n);
        else if (n.nodeType === Node.ELEMENT_NODE) applyLanguage(n);
      }));
    }).observe(document.body, { childList: true, subtree: true });
    applyLanguage();
  }

  /* ================================================================
     1. REFERENCE DATA POOLS (realistic telecom / Djezzy identities)
     ================================================================ */
  const supervisors = [
    { email: 'amina.east@djezzy.dz',      zone: 'East Region' },
    { email: 'karim.benaissa@djezzy.dz',  zone: 'East Region' },
    { email: 'yasmine.hamdi@djezzy.dz',   zone: 'East Region' },
    { email: 'ahmed.saidi@djezzy.dz',     zone: 'East Region' },
    { email: 'malik.center@djezzy.dz',    zone: 'North Region' },
    { email: 'nadia.bouzid@djezzy.dz',    zone: 'North Region' },
    { email: 'farid.center@djezzy.dz',    zone: 'North Region' },
    { email: 'lamia.hadjar@djezzy.dz',    zone: 'North Region' },
    { email: 'sofiane.west@djezzy.dz',    zone: 'West Region' },
    { email: 'wassim.belkacem@djezzy.dz', zone: 'West Region' },
    { email: 'imane.cherif@djezzy.dz',    zone: 'West Region' },
    { email: 'rachid.benmoussa@djezzy.dz',zone: 'West Region' },
    { email: 'bilal.south@djezzy.dz',     zone: 'South Region' },
    { email: 'meriem.dahmani@djezzy.dz',  zone: 'South Region' },
    { email: 'tarek.messaoudi@djezzy.dz', zone: 'South Region' }
  ];

  const suspiciousSenders = [
    { email: 'gmail.contact92@gmail.com', zone: 'East Region' },
    { email: 'no-reply@promo-deals.biz',  zone: 'West Region' },
    { email: 'unknown.user@webmail.dz',   zone: 'North Region' }
  ];

  const REQUEST_TYPES = {
    ACCOUNT_ACCESS: { key: 'Locked Account', icon: '🔐', endpoint: '/v1/pos/unlock', apiField: 'pdv_code', conf: [78, 97], dur: [900, 2200] },
    RESET:         { key: 'Password Reset', icon: '🔑', endpoint: '/v1/pass/reset', apiField: 'pdv_code', conf: [80, 98], dur: [700, 1900] },
    OTP:           { key: 'OTP Update', icon: '📱', endpoint: '/v1/otp/update', apiField: 'msisdn', conf: [75, 96], dur: [900, 2100] },
    SERVICE_PROVISIONING: { key: 'VPN Creation', icon: '🛠️', endpoint: '/v1/vpn/create', apiField: 'pdv_code', conf: [70, 94], dur: [1400, 3200] },
    IRRELEVANT:    { key: 'Irrelevant', icon: '🗑️', endpoint: null, apiField: null, conf: [88, 99], dur: [150, 420] }
  };

  const pdvCode = () => String(rnd(10000000, 99999999));
  const msisdn = () => `0${rnd(5,7)}${rnd(10,99)} ${rnd(10,99)} ${rnd(10,99)} ${rnd(10,99)}`;

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

  /* ================================================================
     2. STATE
     ================================================================ */
  let isAgentActive = true;
  let simulationTimer = null;
  let reqSeq = 20482;
  const USERS_KEY = 'snoc-dashboard-users';
  const SESSION_KEY = 'snoc-dashboard-session';
  let currentUser = null;
  let pendingTreatment = null;

  function getUsers() {
    const saved = JSON.parse(localStorage.getItem(USERS_KEY) || 'null');
    return saved || [{ name: 'SNOC Administrator', username: 'admin', role: 'admin', password: 'Admin@123' }, { name: 'TechSupport Ops', username: 'supervisor', role: 'supervisor', password: 'Supervisor@123' }];
  }
  function saveUsers(users) { localStorage.setItem(USERS_KEY, JSON.stringify(users)); }
  function renderUsers() {
    const body = document.getElementById('users-table-body'); if (!body) return;
    body.innerHTML = getUsers().map(user => `<tr><td>${user.name}</td><td>${user.username}</td><td>${user.role}</td><td><button class="whitelist-remove-btn reset-password-btn" data-user="${user.username}">Reset password</button></td></tr>`).join('');
    body.querySelectorAll('.reset-password-btn').forEach(btn => btn.addEventListener('click', () => { const password = prompt(`New password for ${btn.dataset.user} (at least 8 characters):`); if (!password || password.length < 8) return; const users = getUsers(); users.find(u => u.username === btn.dataset.user).password = password; saveUsers(users); alert('Password updated.'); }));
  }
  function applySession(user) {
    currentUser = user;
    document.getElementById('login-overlay').hidden = true;
    document.getElementById('app-container').hidden = false;
    document.getElementById('skeleton-screen').style.display = 'none';
    document.getElementById('current-username').textContent = user.name;
    document.getElementById('current-user-role').textContent = user.role === 'admin' ? 'Dashboard administrator' : 'Djezzy SNOC supervisor';
    document.querySelectorAll('.admin-only').forEach(el => el.style.display = user.role === 'admin' ? '' : 'none');
    renderUsers();
  }

  let stats = {
    emailsProcessed: 0,
    successOps: 0,
    escalations: 0,
    rejectedEmails: 0,
    waitingQueue: 0,
    processingQueue: 0,
    failedQueue: 0,
    timeSavedMinutes: 0,
    recoveredPOS: 0,
    pdvExtracted: 0,
    otpExtracted: 0,
    phoneExtracted: 0,
    missingEntities: 0,
    unauthorizedRequests: 0,
    lowConfidencePredictions: 0,
    totalConfidenceSum: 0,
    confidenceCount: 0,
    hourlyRequests: Array(24).fill(0),
    weeklyRequests: Array(7).fill(0),
    blockingEast: 0, blockingCenter: 0, blockingWest: 0
  };

  let requestPool = [];   // full history (audit + timeline share this)
  let activeAlerts = [];
  let backendMode = false;

  let intentChart, confidenceChart, hourlyChart, weeklyChart;

  const BACKEND_INTENT_LABELS = {
    unlock_account: 'Locked Account',
    reset_password: 'Password Reset',
    reactivate_account: 'Locked Account',
    update_otp_phone: 'OTP Update',
    create_pdv_account: 'VPN Creation',
    create_vpn_account: 'VPN Creation',
    account_access: 'Locked Account',
    service_provisioning: 'VPN Creation',
    unknown: 'Unknown'
  };

  const BACKEND_INTENT_ICONS = {
    unlock_account: '🔐',
    reset_password: '🔑',
    reactivate_account: '🔐',
    update_otp_phone: '📱',
    create_pdv_account: '🛠️',
    create_vpn_account: '🛠️',
    account_access: '🔐',
    service_provisioning: '🛠️',
    unknown: '🧠'
  };

  function normalizeConfidence(value) {
    if (value === null || value === undefined || value === '') return 84;
    const num = Number(value);
    if (!Number.isFinite(num)) return 84;
    return num > 1 ? num : Math.round(num * 100);
  }

  function normalizeStatus(value) {
    const normalized = String(value || '').toLowerCase();
    if (['success', 'auto_execute'].includes(normalized)) return 'Success';
    if (['escalate', 'escalated'].includes(normalized)) return 'Escalated';
    if (['reject', 'rejected'].includes(normalized)) return 'Rejected';
    if (['processing', 'clarify', 'pending'].includes(normalized)) return 'Processing';
    return 'Processing';
  }

  function normalizeIntentKey(intent) {
    const map = {
      unlock_account: 'ACCOUNT_ACCESS',
      reset_password: 'RESET',
      reactivate_account: 'ACCOUNT_ACCESS',
      update_otp_phone: 'OTP',
      create_pdv_account: 'SERVICE_PROVISIONING',
      create_vpn_account: 'SERVICE_PROVISIONING',
      account_access: 'ACCOUNT_ACCESS',
      service_provisioning: 'SERVICE_PROVISIONING',
      unknown: 'IRRELEVANT'
    };
    const key = String(intent || 'unknown').toLowerCase().trim();
    return map[key] || key.toUpperCase();
  }

  function formatIntentLabel(intent) {
    const key = String(intent || 'unknown').toLowerCase().trim();
    return BACKEND_INTENT_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, ch => ch.toUpperCase());
  }

  function buildHourlySeries(requests) {
    const hourly = Array.from({ length: 24 }, () => 0);
    requests.forEach(req => {
      const time = req.created_at ? new Date(req.created_at) : null;
      if (time && !Number.isNaN(time.getTime())) hourly[time.getHours()] += 1;
    });
    return hourly;
  }

  function buildWeeklySeries(requests) {
    const weekly = Array.from({ length: 7 }, () => 0);
    requests.forEach(req => {
      const time = req.created_at ? new Date(req.created_at) : null;
      if (time && !Number.isNaN(time.getTime())) weekly[(time.getDay() + 6) % 7] += 1;
    });
    return weekly;
  }

  function mapBackendRecord(record, index = 0) {
    const status = normalizeStatus(record.request_status || record.decision || record.execution_status);
    const confidence = normalizeConfidence(record.confidence);
    const intentName = formatIntentLabel(record.intent || record.request_type || 'unknown');
    const icon = BACKEND_INTENT_ICONS[String(record.intent || record.request_type || 'unknown').toLowerCase().trim()] || '🧠';
    const entities = record.entities || {};
    const pdv = entities.pdv_code || entities.pdv || null;
    const phone = entities.phone_number || entities.phone || null;
    const createdAt = record.created_at ? new Date(record.created_at) : new Date();
    const zone = record.zone || 'Unknown';
    const entityLabel = status === 'Escalated' ? (pdv || 'Missing') : (pdv || '—');

    return {
      id: record.request_id || `SNOC-BE-${index + 1}`,
      typeKey: normalizeIntentKey(record.intent || record.request_type),
      intent: intentName,
      icon,
      sender: record.sender || 'unknown',
      zone,
      confidence,
      status,
      time: fmtTime(createdAt),
      dateFull: fmtDate(createdAt),
      created_at: record.created_at || null,
      duration: status === 'Success' ? '1.2s' : status === 'Processing' ? '—' : '—',
      durationMs: 0,
      pdv: pdv || null,
      phone: phone || null,
      entity: entityLabel,
      action: status === 'Success' ? 'API: ' + intentName : status === 'Escalated' ? 'Human Review' : status === 'Rejected' ? 'Drop' : 'In Progress',
      emailBody: record.body_text || record.cleaned_text || 'No email body available',
      cleanedBody: record.cleaned_text || '',
      reasons: buildReasons(record.intent || record.request_type || 'unknown', status, pdv, confidence, record.sender || 'unknown'),
      apiRequest: record.metadata && record.metadata.execution_details ? { endpoint: '/api/process-email', payload: entities } : null,
      apiResponse: record.metadata && record.metadata.execution_details ? record.metadata.execution_details : null,
      replySubj: record.reply_subject || (status === 'Rejected' ? null : `Re: ${record.subject || intentName}`),
      replyBody: record.reply_text || null,
      treatment: record.treatment || null,
      lang: record.detected_language === 'en' ? 'English (EN)' : record.detected_language === 'ar' ? 'Arabic (AR)' : 'French (FR)'
    };
  }

  function updateAgentUI() {
    const indicator = document.getElementById('agent-btn-indicator');
    const text = document.getElementById('agent-btn-text');
    const statusLabel = document.getElementById('sys-status-label');
    const bubble = document.getElementById('status-bubble');
    const bubbleText = document.getElementById('status-bubble-text');

    if (indicator) indicator.classList.toggle('active', isAgentActive);
    if (text) text.textContent = isAgentActive ? 'Pause Agent' : 'Resume Agent';

    if (backendMode) {
      if (statusLabel) statusLabel.textContent = isAgentActive ? 'LIVE 🟢' : 'PAUSED 🟠';
    } else {
      if (statusLabel) statusLabel.textContent = isAgentActive ? 'ACTIVE 🟢' : 'PAUSED 🟠';
    }

    if (bubble) bubble.classList.toggle('active', isAgentActive);
    if (bubbleText) bubbleText.textContent = isAgentActive ? 'Agent Active' : 'Agent Paused';
  }

  function applyDashboardPayload(payload) {
    const requests = Array.isArray(payload.requests) ? payload.requests : [];
    const alerts = Array.isArray(payload.alerts) ? payload.alerts : [];
    const statsPayload = payload.stats || {};

    requestPool = requests.map((record, index) => mapBackendRecord(record, index));
    activeAlerts = alerts.map((alert, index) => ({ ...alert, id: alert.id || 'A' + (index + 1) }));

    stats = {
      ...stats,
      emailsProcessed: Number(statsPayload.total_requests || requestPool.length || 0),
      successOps: Number(statsPayload.successful_executions || requestPool.filter(r => r.status === 'Success').length || 0),
      escalations: Number(statsPayload.escalated || requestPool.filter(r => r.status === 'Escalated').length || 0),
      rejectedEmails: Number(statsPayload.rejected || requestPool.filter(r => r.status === 'Rejected').length || 0),
      waitingQueue: Number(statsPayload.pending_requests || 0),
      processingQueue: Number(statsPayload.in_progress || 0),
      failedQueue: Number(statsPayload.failed || 0),
      missingEntities: Number(statsPayload.missing_entities || 0),
      unauthorizedRequests: Number(statsPayload.unauthorized || 0),
      lowConfidencePredictions: Number(statsPayload.low_confidence || 0),
      totalConfidenceSum: requestPool.reduce((sum, req) => sum + req.confidence, 0),
      confidenceCount: requestPool.length || 1,
      hourlyRequests: buildHourlySeries(requestPool),
      weeklyRequests: buildWeeklySeries(requestPool)
    };

    backendMode = true;
    if (payload.agent_active !== undefined) {
      isAgentActive = payload.agent_active;
    }
  }

  async function loadDashboardData() {
    try {
      const response = await fetch('/api/dashboard');
      if (!response.ok) throw new Error('backend unavailable');
      const payload = await response.json();
      applyDashboardPayload(payload);
      const syncEl = document.getElementById('last-sync-time');
      if (syncEl) syncEl.textContent = fmtTime(new Date());
      const sysSyncEl = document.getElementById('sys-last-sync');
      if (sysSyncEl) sysSyncEl.textContent = fmtTime(new Date());
      updateAgentUI();
      generateHeatmap();
      return true;
    } catch (error) {
      console.warn('Backend unavailable, falling back to demo data.', error);
      backendMode = false;
      return false;
    }
  }

  /* ================================================================
     3. DATA GENERATION
     ================================================================ */
  function buildReasons(type, status, pdv, entityVal, sender) {
    const normalizedType = normalizeIntentKey(type);
    if (status === 'Escalated') {
      return [
        `confidence score ${entityVal}% below the 85% automatic decision threshold`,
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
    switch (normalizedType) {
      case 'ACCOUNT_ACCESS': return [`detected account access request`, `extracted valid PDV code ${pdv}`, `sender authorized under zone whitelist`, `matched account access workflow`];
      case 'RESET': return [`detected password reset intent keywords`, `extracted valid PDV code ${pdv}`, `sender authorized under zone whitelist`];
      case 'SERVICE_PROVISIONING': return [`detected service provisioning request`, `extracted PDV code ${pdv} and technician context`, `sender authorized under zone whitelist`];
      case 'OTP': return [`detected OTP update intent`, `extracted valid MSISDN and PDV code ${pdv}`, `sender authorized under zone whitelist`];
      default: return [`detected actionable support intent ${type || 'unknown'} and routed to the workflow`];
    }
  }

  function generateRequest(atTime, forceType, forceStatus) {
    const typeKeys = Object.keys(REQUEST_TYPES);
    // weighted distribution favouring account access / reset flows
    const weighted = ['ACCOUNT_ACCESS','ACCOUNT_ACCESS','ACCOUNT_ACCESS','RESET','RESET','OTP','SERVICE_PROVISIONING','SERVICE_PROVISIONING','IRRELEVANT'];
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

    const templateKey = typeKey === 'ACCOUNT_ACCESS' ? 'LOCKED' : typeKey === 'SERVICE_PROVISIONING' ? 'VPN' : typeKey;
    const emailBody = typeKey === 'OTP' ? emailTemplatesFR.OTP(pdv, phone) : emailTemplatesFR[templateKey](pdv);
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
        ACCOUNT_ACCESS: 'Account access request completed successfully',
        RESET: 'Password reset link generated',
        SERVICE_PROVISIONING: 'Service provisioning completed successfully',
        OTP: 'OTP contact number updated'
      }[typeKey]
    } : (status === 'Success' ? null : null);

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

  function seedRequestPool() {
    requestPool = [];
  }

  function seedAlerts() {
    activeAlerts = [];
  }

  /* ================================================================
     4. CHARTS
     ================================================================ */
  function computeIntentCounts() {
    const counts = {};
    Object.values(REQUEST_TYPES).forEach(t => counts[t.key] = 0);
    requestPool.forEach(r => {
      const key = formatIntentLabel(r.intent);
      counts[key] = (counts[key] || 0) + 1;
    });
    return counts;
  }

  function computeConfidenceBuckets() {
    const buckets = [0, 0, 0, 0, 0]; // <70, 70-80, 80-90, 90-95, 95-100
    requestPool.forEach(r => {
      if (r.confidence < 70) buckets[0]++;
      else if (r.confidence < 80) buckets[1]++;
      else if (r.confidence < 90) buckets[2]++;
      else if (r.confidence < 95) buckets[3]++;
      else buckets[4]++;
    });
    return buckets;
  }

  function computeRegionCounts() {
    const counts = { 'East Region': 0, 'North Region': 0, 'West Region': 0, 'South Region': 0, Unknown: 0 };
    requestPool.forEach(r => counts[r.zone] = (counts[r.zone] || 0) + 1);
    return counts;
  }

  const regionColors = ['#E30613', '#0D0E10', '#4A5568', '#94A3B8', '#CBD5E1'];

  function renderRegionDistribution() {
    const list = document.getElementById('region-dist-list');
    if (!list) return;

    const regionCounts = computeRegionCounts();
    const entries = Object.entries(regionCounts).sort((a, b) => b[1] - a[1]);
    const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;

    list.innerHTML = entries.map(([label, count], i) => {
      const pct = Math.round((count / total) * 100);
      const color = regionColors[i % regionColors.length];
      return `
        <div class="region-dist-row">
          <div class="region-dist-rank" style="color:${color};border-color:${color};">${i + 1}</div>
          <div class="region-dist-main">
            <div class="region-dist-top">
              <span class="region-dist-label">${label}</span>
              <span class="region-dist-value">${count} <span class="region-dist-pct">(${pct}%)</span></span>
            </div>
            <div class="region-dist-track">
              <div class="region-dist-fill" style="width:${pct}%;background:${color};"></div>
            </div>
          </div>
        </div>`;
    }).join('');
  }

  function initCharts() {
    Chart.defaults.font.family = 'Inter, sans-serif';
    Chart.defaults.color = '#64748B';

    const intentCounts = computeIntentCounts();
    const intentLabels = Object.keys(intentCounts);
    const intentColors = ['#E30613', '#0D0E10', '#4A5568', '#94A3B8', '#F59E0B', '#3B82F6', '#CBD5E1'];

    const ctxIntents = document.getElementById('chart-intents');
    if (ctxIntents) {
      intentChart = new Chart(ctxIntents, {
        type: 'doughnut',
        data: { labels: intentLabels, datasets: [{ data: intentLabels.map(l => intentCounts[l]), backgroundColor: intentColors, borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { display: false } } }
      });
      const legendList = document.getElementById('intent-legend-list');
      if (legendList) {
        legendList.innerHTML = intentLabels.map((label, i) =>
          `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
             <span style="display:flex;align-items:center;"><span style="width:10px;height:10px;background:${intentColors[i]};display:inline-block;margin-right:8px;border-radius:2px;"></span><span style="font-size:12px;">${label}</span></span>
             <span style="font-size:12px;font-weight:600;color:#64748B;">${intentCounts[label]}</span>
           </div>`
        ).join('');
      }
    }

    const buckets = computeConfidenceBuckets();
    const ctxConf = document.getElementById('chart-confidence');
    if (ctxConf) {
      confidenceChart = new Chart(ctxConf, {
        type: 'bar',
        data: { labels: ['<70%', '70-80%', '80-90%', '90-95%', '95-100%'], datasets: [{ data: buckets, backgroundColor: '#E30613', borderRadius: 4 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
          scales: { y: { grid: { color: '#F1F5F9' } }, x: { grid: { display: false } } } }
      });
    }

    renderRegionDistribution();

    const ctxHourly = document.getElementById('chart-hourly');
    if (ctxHourly) {
      const hours = Array.from({ length: 24 }, (_, i) => pad2(i));
      hourlyChart = new Chart(ctxHourly, {
        type: 'line',
        data: { labels: hours, datasets: [{ data: stats.hourlyRequests, borderColor: '#E30613', backgroundColor: 'rgba(227,6,19,0.08)', fill: true, tension: 0.4, pointRadius: 2, pointHoverRadius: 5 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, grid: { color: '#F1F5F9' } }, x: { grid: { display: false } } } }
      });
    }

    const ctxWeekly = document.getElementById('chart-weekly');
    if (ctxWeekly) {
      weeklyChart = new Chart(ctxWeekly, {
        type: 'bar',
        data: { labels: ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'], datasets: [{ data: stats.weeklyRequests, backgroundColor: '#E30613', borderRadius: 4 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, grid: { color: '#F1F5F9' } }, x: { grid: { display: false } } } }
      });
    }
  }

  function refreshCharts() {
    if (intentChart) {
      const counts = computeIntentCounts();
      intentChart.data.datasets[0].data = intentChart.data.labels.map(l => counts[l]);
      intentChart.update('none');
      const legendList = document.getElementById('intent-legend-list');
      if (legendList) {
        const colors = intentChart.data.datasets[0].backgroundColor;
        legendList.innerHTML = intentChart.data.labels.map((label, i) =>
          `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
             <span style="display:flex;align-items:center;"><span style="width:10px;height:10px;background:${colors[i]};display:inline-block;margin-right:8px;border-radius:2px;"></span><span style="font-size:12px;">${label}</span></span>
             <span style="font-size:12px;font-weight:600;color:#64748B;">${counts[label]}</span>
           </div>`).join('');
      }
    }
    if (confidenceChart) { confidenceChart.data.datasets[0].data = computeConfidenceBuckets(); confidenceChart.update('none'); }
    renderRegionDistribution();
    if (hourlyChart) { hourlyChart.data.datasets[0].data = stats.hourlyRequests; hourlyChart.update('none'); }
    if (weeklyChart) { weeklyChart.data.datasets[0].data = stats.weeklyRequests; weeklyChart.update('none'); }
  }

  /* ================================================================
     5. HEATMAP
     ================================================================ */
  function generateHeatmap() {
    const grid = document.getElementById('heatmap-grid');
    if (!grid) return;
    if (!requestPool.length) {
      grid.style.display = 'flex';
      grid.style.alignItems = 'center';
      grid.style.justifyContent = 'center';
      grid.style.minHeight = '140px';
      grid.style.color = '#64748B';
      grid.innerHTML = '<div>No request traffic yet — the heatmap will populate from live workflow data.</div>';
      return;
    }

    let heatmapData = Array.from({ length: 7 }, () => Array(24).fill(0));
    requestPool.forEach(req => {
      const time = req.created_at ? new Date(req.created_at) : null;
      if (time && !Number.isNaN(time.getTime())) {
        heatmapData[(time.getDay() + 6) % 7][time.getHours()] += 1;
      }
    });
    grid.style.display = 'grid';
    grid.style.gridTemplateColumns = 'auto repeat(24, 1fr)';
    grid.style.gap = '2px';
    grid.innerHTML = '<div></div>';
    for (let h = 0; h < 24; h++) grid.innerHTML += `<div class="heatmap-hour-label" style="font-size:10px;text-align:center;">${pad2(h)}</div>`;
    const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    for (let d = 0; d < 7; d++) {
      grid.innerHTML += `<div class="heatmap-label" style="font-size:12px;padding-right:8px;text-align:right;">${days[d]}</div>`;
      for (let h = 0; h < 24; h++) {
        let val = heatmapData[d][h];
        let heatClass = 'heat-0';
        if (val >= 25) heatClass = 'heat-5'; else if (val >= 19) heatClass = 'heat-4';
        else if (val >= 14) heatClass = 'heat-3'; else if (val >= 9) heatClass = 'heat-2';
        else if (val >= 4) heatClass = 'heat-1';
        grid.innerHTML += `<div class="heatmap-cell ${heatClass}" title="${days[d]} ${pad2(h)}:00 — ${val} requests" style="border-radius:2px;"></div>`;
      }
    }
  }

  /* ================================================================
     6. RENDERERS
     ================================================================ */
  function statusBadgeClass(status) {
    return { Success: 'badge-success', Processing: 'badge-processing', Escalated: 'badge-escalated', Rejected: 'badge-rejected' }[status] || 'badge-warning';
  }

  function renderTimeline() {
    ['timeline-list', 'audit-timeline-list'].forEach(containerId => {
      const container = document.getElementById(containerId);
      if (!container) return;
      const rows = requestPool.slice(0, 22);
      container.innerHTML = rows.map(req => `
        <div class="timeline-row" data-id="${req.id}">
          <div class="time-col">${req.time}</div>
          <div class="sender-col">${req.sender}</div>
          <div class="intent-col">${req.icon} ${req.intent}</div>
          <div class="pdv-col">${req.entity}</div>
          <div class="duration-col">${req.duration}</div>
          <div><span class="badge ${statusBadgeClass(req.status)}">${req.status}</span></div>
          <div style="text-align:right;color:#94A3B8;">›</div>
        </div>
      `).join('');
      container.querySelectorAll('.timeline-row').forEach(row => {
        row.addEventListener('click', () => {
          const req = requestPool.find(r => r.id === row.getAttribute('data-id'));
          if (req) openDecisionInspector(req);
        });
      });
    });
  }

  function filterRequests(filterType, searchQuery) {
    return requestPool.filter(req => {
      let matchFilter = true;
      if (filterType && filterType !== 'all') {
        if (filterType === 'Escalated') matchFilter = req.status === 'Escalated';
        else matchFilter = req.intent.toLowerCase().includes(filterType.toLowerCase());
      }
      const q = (searchQuery || '').toLowerCase().trim();
      const matchSearch = q === '' ||
        req.id.toLowerCase().includes(q) || req.sender.toLowerCase().includes(q) ||
        req.intent.toLowerCase().includes(q) || (req.pdv && req.pdv.includes(q)) ||
        (req.phone && req.phone.includes(q)) || req.status.toLowerCase().includes(q) ||
        req.zone.toLowerCase().includes(q);
      return matchFilter && matchSearch;
    });
  }

  function renderAuditTableGeneric(opts) {
    const tbody = document.getElementById(opts.tbodyId);
    if (!tbody) return;

    let filterType = opts.filterType;
    if (filterType === undefined) {
      const activeBtn = document.querySelector(opts.filterScopeSelector + ' .filter-btn.active');
      filterType = activeBtn ? activeBtn.getAttribute('data-filter') : 'all';
    }
    let searchQuery = opts.searchQuery;
    if (searchQuery === undefined) {
      const searchInput = document.getElementById('global-search');
      searchQuery = searchInput ? searchInput.value : '';
    }

    const filtered = filterRequests(filterType, searchQuery);

    const displayedCount = document.getElementById(opts.displayedId);
    const totalCount = document.getElementById(opts.totalId);
    if (displayedCount) displayedCount.textContent = Math.min(filtered.length, 40);
    if (totalCount) totalCount.textContent = requestPool.length;

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:#94A3B8;">🤖 No requests match this filter</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.slice(0, 40).map(req => `
      <tr data-id="${req.id}" style="cursor:pointer;">
        <td>${req.time}</td>
        <td>${req.sender}</td>
        <td>${req.zone}</td>
        <td>${req.icon} ${req.intent}</td>
        <td>${req.confidence}%</td>
        <td>${req.pdv || '—'}</td>
        <td>${req.duration}</td>
        <td><span class="badge ${statusBadgeClass(req.status)}">${req.status}</span></td>
        <td><button class="actions-btn" title="Inspect">🔍</button></td>
      </tr>
    `).join('');

    tbody.querySelectorAll('tr[data-id]').forEach(tr => {
      tr.addEventListener('click', () => {
        const req = requestPool.find(r => r.id === tr.getAttribute('data-id'));
        if (req) openDecisionInspector(req);
      });
    });
  }

  function renderAuditTable(filterType, searchQuery) {
    renderAuditTableGeneric({
      tbodyId: 'audit-table-body',
      displayedId: 'displayed-rows-count',
      totalId: 'total-rows-count',
      filterScopeSelector: '#quick-filters-row',
      filterType, searchQuery
    });
  }

  function renderAuditPageTable(filterType, searchQuery) {
    renderAuditTableGeneric({
      tbodyId: 'audit-page-table-body',
      displayedId: 'audit-page-displayed-rows-count',
      totalId: 'audit-page-total-rows-count',
      filterScopeSelector: '#audit-page-filters',
      filterType, searchQuery
    });
  }

  /* ================================================================
     6b. OPERATIONS — ESCALATION QUEUE (manual treatment)
     ================================================================ */
  function renderEscalationQueue() {
    const tbody = document.getElementById('escalation-queue-body');
    if (!tbody) return;

    const escalated = requestPool.filter(r => r.status === 'Escalated' || r.treatment);

    const countEl = document.getElementById('escalation-queue-count');
    const pendingCount = escalated.filter(r => r.status === 'Escalated').length;
    if (countEl) countEl.textContent = `${pendingCount} Pending · ${escalated.length - pendingCount} Treated`;
    const navBadge = document.getElementById('nav-operations-badge');
    if (navBadge) navBadge.textContent = escalated.length;

    if (escalated.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:40px;color:#94A3B8;">🎉 No escalated requests — all clear!</td></tr>';
      return;
    }

    tbody.innerHTML = escalated.slice(0, 60).map(req => `
      <tr data-id="${req.id}">
        <td>${req.time}</td>
        <td>${req.sender}</td>
        <td>${req.zone}</td>
        <td>${req.icon} ${req.intent}</td>
        <td>${req.confidence}%</td>
        <td>${req.entity}</td>
        <td class="escalation-reason-cell">${req.reasons[0]}</td>
        <td class="treatment-cell"><strong>${req.treatment ? req.treatment.decision.toUpperCase() + ' by ' + req.treatment.by : 'Pending'}</strong>${req.treatment ? `<span class="treatment-note">${req.treatment.note || 'No note'} · ${req.treatment.at}</span>` : ''}</td>
        <td class="escalation-actions-cell">
          <button class="btn-treat btn-treat-approve" data-id="${req.id}" data-decision="approve" title="Approve &amp; Execute">✔ Approve</button>
          <button class="btn-treat btn-treat-reject" data-id="${req.id}" data-decision="reject" title="Reject Request">✖ Reject</button>
          <button class="actions-btn escalation-inspect-btn" data-id="${req.id}" title="Inspect">🔍</button>
        </td>
      </tr>
    `).join('');

    tbody.querySelectorAll('.btn-treat').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openTreatmentDialog(btn.getAttribute('data-id'), btn.getAttribute('data-decision'));
      });
    });
    tbody.querySelectorAll('.escalation-inspect-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const req = requestPool.find(r => r.id === btn.getAttribute('data-id'));
        if (req) openDecisionInspector(req);
      });
    });
  }

  function refreshAllViews() {
    recalcAggregateStats();
    renderTimeline();
    renderAuditTable();
    renderAuditPageTable();
    renderEscalationQueue();
    renderAlerts();
    refreshCharts();
    updateHealthKPIs();
    updateQueueBoard();
    updateQualityMetrics();
    updateDashboardKPIs();
    updateParamMetrics();
  }

  function openTreatmentDialog(id, decision) {
    pendingTreatment = { id, decision };
    const req = requestPool.find(r => r.id === id), dialog = document.getElementById('treatment-dialog');
    if (!req || req.status !== 'Escalated') return;
    document.getElementById('treatment-title').textContent = decision === 'approve' ? 'Approve and treat escalation' : 'Reject escalation';
    document.getElementById('treatment-description').textContent = `${req.intent} from ${req.sender}. Your name and optional note will be saved in the audit trail.`;
    document.getElementById('treatment-note').value = '';
    dialog.showModal();
  }

  function resolveEscalatedRequest(id, decision, note = '') {
    const req = requestPool.find(r => r.id === id);
    if (!req) return;

    req.status = decision === 'approve' ? 'Success' : 'Rejected';
    req.treatment = { decision, by: currentUser ? currentUser.name : 'Unknown user', at: fmtDate(new Date()), note: note.trim() };
    req.action = decision === 'approve' ? `Manually Approved — ${req.intent}` : 'Manually Rejected by Supervisor';
    req.reasons = decision === 'approve'
      ? [`manually approved by supervisor`, ...req.reasons]
      : [`manually rejected by supervisor`, ...req.reasons];

    if (decision === 'approve') {
      req.replySubj = `Re: ${req.intent} — PDV ${req.pdv || ''} RESOLVED`;
      req.replyBody = `Bonjour,\n\nVotre demande (${req.intent}) a été approuvée manuellement par un superviseur et traitée avec succès.\n\nCordialement,\nSNOC AI Agent`;
    } else {
      req.replySubj = `Re: ${req.intent} — Request Closed`;
      req.replyBody = `Bonjour,\n\nVotre demande (${req.intent}) a été examinée et rejetée par un superviseur. Merci de nous contacter si vous pensez qu'il s'agit d'une erreur.\n\nCordialement,\nSNOC AI Agent`;
    }

    refreshAllViews();

    logTerminal([{
      text: `[${fmtTime(new Date())}] ${decision === 'approve' ? '✔ Escalated request manually approved' : '✖ Escalated request manually rejected'} — ${req.id} (${req.sender})`,
      cls: decision === 'approve' ? 'text-success' : 'text-danger'
    }]);
  }

  function renderAlerts() {
    const listEl = document.getElementById('operational-alerts-list');
    const dropdownList = document.getElementById('dropdown-alerts-list');
    const active = activeAlerts.filter(a => a.status === 'Active');

    const countEl = document.getElementById('alerts-count');
    const badgeEl = document.getElementById('alert-badge-count');
    if (countEl) countEl.textContent = active.length + ' Active';
    if (badgeEl) badgeEl.textContent = active.length;

    const buildRow = (a, actionable) => `
      <div class="alert-item ${actionable ? 'alert-actionable' : ''}" data-alert-row-id="${a.id}">
        <span class="alert-severity sev-${a.severity}"></span>
        <span class="alert-item-content">${a.message}</span>
        <span class="alert-item-region">${a.region}</span>
        <span class="alert-item-time">${a.time}</span>
        <button class="alert-dismiss-btn" data-alert-id="${a.id}">Dismiss</button>
        ${actionable ? `<span class="alert-review-btn">Review in Operations ›</span>` : `<span></span>`}
      </div>
    `;

    const html = active.map(a => buildRow(a, true)).join('');
    if (listEl) listEl.innerHTML = html || '<div style="padding:20px;color:#94A3B8;text-align:center;">No active alerts 🎉</div>';
    if (dropdownList) dropdownList.innerHTML = active.map(a => buildRow(a, false)).join('') || '<div style="padding:16px;color:#94A3B8;text-align:center;">No active alerts</div>';

    document.querySelectorAll('.alert-dismiss-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = e.target.getAttribute('data-alert-id');
        const alert = activeAlerts.find(a => a.id === id);
        if (alert) { alert.status = 'Resolved'; renderAlerts(); }
      });
    });

    if (listEl) {
      listEl.querySelectorAll('.alert-item.alert-actionable').forEach(row => {
        row.addEventListener('click', () => {
          if (typeof switchPage === 'function') switchPage('emails');
          const liveFeedBtn = document.querySelector('#section-emails .param-subtab-btn[data-param-tab="live-feed"]');
          if (liveFeedBtn) liveFeedBtn.click();
        });
      });
    }
  }

  function logTerminal(lines) {
    const term = document.getElementById('console-terminal');
    if (!term) return;
    lines.forEach(l => {
      const div = document.createElement('div');
      div.className = 'console-line ' + (l.cls || '');
      div.textContent = l.text;
      term.appendChild(div);
    });
    while (term.children.length > 80) term.removeChild(term.firstChild);
    term.scrollTop = term.scrollHeight;
  }

  function seedConsole() {
    const term = document.getElementById('console-terminal');
    if (!term) return;
    term.innerHTML = '';
    const recent = requestPool.slice(0, 8).slice().reverse();
    recent.forEach(req => {
      const lines = [
        { text: `[${req.time}] Email received from ${req.sender} (${req.zone})`, cls: 'text-muted' },
        { text: `[${req.time}] Sender verification ${req.status === 'Escalated' && req.reasons.some(r=>r.includes('whitelist')) ? 'FAILED — not in whitelist' : 'OK'}` },
        { text: `[${req.time}] Intent classified: ${req.intent} (confidence ${req.confidence}%)` },
        { text: `[${req.time}] Entities extracted: ${req.entity}` },
      ];
      if (req.status === 'Success') {
        lines.push({ text: `[${req.time}] API request executed → ${req.apiRequest ? req.apiRequest.endpoint : 'n/a'}` });
        lines.push({ text: `[${req.time}] ✔ Success response received (${req.duration})`, cls: 'text-success' });
      } else if (req.status === 'Escalated') {
        lines.push({ text: `[${req.time}] ⚠ Escalated to human supervisor — ${req.reasons[0]}`, cls: 'text-warning' });
      } else if (req.status === 'Rejected') {
        lines.push({ text: `[${req.time}] ✖ Invalid intent — email rejected, no reply sent`, cls: 'text-danger' });
      } else {
        lines.push({ text: `[${req.time}] ⏳ Awaiting SNOC API response...`, cls: 'text-muted' });
      }
      logTerminal(lines);
    });
    logTerminal([{ text: `[${fmtTime(new Date())}] SYSTEM STREAM STABLE — awaiting next batch...`, cls: 'text-muted' }]);
  }

  /* ================================================================
     7. KPI / QUEUE / QUALITY METRICS
     ================================================================ */
  function recalcAggregateStats() {
    const totalRequests = requestPool.length;
    const successful = requestPool.filter(r => r.status === 'Success').length;
    const escalations = requestPool.filter(r => r.status === 'Escalated').length;
    const rejected = requestPool.filter(r => r.status === 'Rejected').length;

    stats.emailsProcessed = totalRequests;
    stats.successOps = successful;
    stats.escalations = escalations;
    stats.rejectedEmails = rejected;
    stats.waitingQueue = totalRequests > 0 ? 1 : 0;
    stats.processingQueue = 0;
    stats.failedQueue = 0;
    stats.totalConfidenceSum = requestPool.reduce((s, r) => s + r.confidence, 0);
    stats.confidenceCount = totalRequests || 1;
    stats.hourlyRequests = buildHourlySeries(requestPool);
    stats.weeklyRequests = buildWeeklySeries(requestPool);
  }

  function updateHealthKPIs() {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    const automationRate = stats.emailsProcessed ? ((stats.successOps / stats.emailsProcessed) * 100).toFixed(1) : '0.0';
    set('kpi-automation', automationRate + '%');
    set('sys-automation-rate', automationRate + '%');
    set('kpi-emails', commas(stats.emailsProcessed));
    set('sys-emails-processed', commas(stats.emailsProcessed));
    set('sys-queue-count', stats.waitingQueue + stats.processingQueue);
    set('kpi-latency', backendMode ? 'Recorded per request' : (rndFloat(1.3, 2.1, 1)) + 's');
    set('kpi-escalations', commas(stats.escalations));
    set('kpi-api-health', backendMode ? 'Not configured' : rndFloat(96.5, 99.2, 1) + '%');
  }

  function updateDashboardKPIs() {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('dash-auto-resolved', commas(stats.successOps));
    set('dash-escalated', commas(stats.escalations));
    set('dash-rejected', commas(stats.rejectedEmails));
  }

  function renderParamIntentList() {
    const container = document.getElementById('param-intent-list');
    if (!container) return;
    const counts = computeIntentCounts();
    const max = Math.max(1, ...Object.values(counts));
    container.innerHTML = Object.entries(counts).map(([name, count]) => `
      <div class="param-intent-row">
        <span class="intent-name">${name}</span>
        <span class="intent-bar-bg"><span class="intent-bar-fill" style="width:${(count / max * 100).toFixed(0)}%;"></span></span>
        <span class="intent-count">${commas(count)}</span>
      </div>
    `).join('');
  }

  function updateParamMetrics() {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    const successRate = stats.emailsProcessed ? (stats.successOps / stats.emailsProcessed * 100).toFixed(1) : '0.0';
    const failRate = stats.emailsProcessed ? (stats.rejectedEmails / stats.emailsProcessed * 100).toFixed(1) : '0.0';
    const automationRate = stats.emailsProcessed ? ((stats.successOps / stats.emailsProcessed) * 100).toFixed(1) : '0.0';
    set('param-total-processed', commas(stats.emailsProcessed));
    set('param-avg-confidence', (stats.totalConfidenceSum / stats.confidenceCount).toFixed(1) + '%');
    set('param-low-confidence', stats.lowConfidencePredictions);
    set('param-success-rate', successRate + '%');
    set('param-failure-rate', failRate + '%');
    set('param-automation-rate', automationRate + '%');
    set('param-avg-processing', backendMode ? 'Not tracked' : rndFloat(1.4, 1.9, 1) + 's');
    renderParamIntentList();
  }

  /* ================================================================
     7b. WHITELIST MANAGEMENT
     ================================================================ */
  function renderWhitelist() {
    const tbody = document.getElementById('whitelist-table-body');
    if (!tbody) return;
    tbody.innerHTML = supervisors.map((s, i) => `
      <tr>
        <td>${s.email}</td>
        <td>${s.zone}</td>
        <td><button class="whitelist-remove-btn" data-idx="${i}">Remove</button></td>
      </tr>
    `).join('');
    tbody.querySelectorAll('.whitelist-remove-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.getAttribute('data-idx'), 10);
        supervisors.splice(idx, 1);
        renderWhitelist();
      });
    });
  }

  function updateQueueBoard() {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('q-waiting', stats.waitingQueue);
    set('q-processing', stats.processingQueue);
    set('q-completed', commas(stats.successOps));
    set('q-failed', stats.failedQueue);
    set('q-escalated', commas(stats.escalations));
  }

  function updateQualityMetrics() {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    const successRate = stats.emailsProcessed ? (stats.successOps / stats.emailsProcessed * 100).toFixed(1) : '0.0';
    const failRate = stats.emailsProcessed ? (stats.failedQueue / stats.emailsProcessed * 100).toFixed(1) : '0.0';
    set('qm-success-rate', successRate + '%');
    set('qm-failure-rate', failRate + '%');
    set('qm-avg-processing', backendMode ? 'Not tracked' : rndFloat(1.4, 1.9, 1) + 's');
    set('qm-avg-api', backendMode ? 'Not tracked' : rnd(600, 780) + 'ms');
    set('qm-low-confidence', stats.lowConfidencePredictions);
    set('qm-missing-entities', stats.missingEntities);
    set('qm-unauthorized', stats.unauthorizedRequests);
    set('qm-rejected', commas(stats.rejectedEmails));
    set('qm-escalation-count', commas(stats.escalations));
    set('qm-avg-confidence', (stats.totalConfidenceSum / stats.confidenceCount).toFixed(1) + '%');
  }

  /* ================================================================
     8. DECISION INSPECTOR DRAWER
     ================================================================ */
  function openDecisionInspector(req) {
    const drawer = document.getElementById('detail-drawer');
    if (drawer) drawer.classList.add('open');
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

    set('ins-request-id', `Request ID: #${req.id}`);
    set('ins-confidence-pct', req.confidence + '%');
    set('ins-decision-route', req.status === 'Success' ? 'AUTOMATIC RESPONSE' : req.status === 'Escalated' ? 'ESCALATED TO SUPERVISOR' : req.status === 'Processing' ? 'IN PROGRESS' : 'DROPPED — NO ACTION');

    const confEl = document.getElementById('ins-confidence-pct');
    if (confEl) confEl.className = 'val ' + (req.confidence >= 85 ? 'text-success' : 'highlight-red');

    const reasonsList = document.getElementById('ins-reasons-list');
    if (reasonsList) reasonsList.innerHTML = req.reasons.map(r => `<li>${r}</li>`).join('');

    set('ins-email-from', req.sender);
    set('ins-email-subj', (req.intent) + (req.pdv ? ` PDV ${req.pdv}` : ''));
    set('ins-email-date', req.dateFull);
    const bodyEl = document.getElementById('ins-email-body');
    if (bodyEl) bodyEl.innerHTML = req.emailBody.replace(/\n/g, '<br>');
    set('ins-email-cleaned', req.cleanedBody);

    set('ins-extracted-intent', req.intent);
    set('ins-extracted-pdv', req.pdv || 'None');
    set('ins-extracted-otp', req.typeKey === 'OTP' ? 'Parsed from request' : 'None');
    set('ins-extracted-phone', req.phone || 'None');
    set('ins-extracted-lang', req.lang);

    const apiReqEl = document.getElementById('ins-api-request');
    const apiResEl = document.getElementById('ins-api-response');
    if (apiReqEl) apiReqEl.textContent = req.apiRequest ? JSON.stringify(req.apiRequest, null, 2) : '// No API call executed for this request';
    if (apiResEl) apiResEl.textContent = req.apiResponse ? JSON.stringify(req.apiResponse, null, 2) : '// No response payload';

    set('ins-reply-to', req.sender);
    set('ins-reply-subj', req.replySubj || 'No reply sent');
    const replyEl = document.getElementById('ins-reply-body');
    if (replyEl) replyEl.innerHTML = req.replyBody ? req.replyBody.replace(/\n/g, '<br>') : '<span style="color:#94A3B8;">No outgoing reply was generated for this request.</span>';

    updateLifecyclePipeline(req);
  }

  function updateLifecyclePipeline(req) {
    const nodeIds = ['pipe-node-received','pipe-node-whitelist','pipe-node-cleaned','pipe-node-classified','pipe-node-ner','pipe-node-validation','pipe-node-api','pipe-node-reply','pipe-node-completed'];
    let activeCount;
    if (req.status === 'Success') activeCount = 9;
    else if (req.status === 'Escalated') activeCount = req.reasons.some(r => r.includes('whitelist')) ? 2 : 6;
    else if (req.status === 'Processing') activeCount = 6;
    else activeCount = 3; // Rejected

    nodeIds.forEach((id, i) => {
      const node = document.getElementById(id);
      if (!node) return;
      node.classList.toggle('active-node', i < activeCount);
    });

    const times = {
      'pipe-time-received': rnd(8, 20) + ' ms',
      'pipe-time-whitelist': rnd(2, 8) + ' ms',
      'pipe-time-cleaned': rnd(10, 25) + ' ms',
      'pipe-time-classified': rnd(320, 520) + ' ms',
      'pipe-time-ner': rnd(80, 160) + ' ms',
      'pipe-time-validation': rnd(15, 40) + ' ms',
      'pipe-time-api': req.status === 'Success' ? rnd(450, 950) + ' ms' : '—',
      'pipe-time-reply': req.status === 'Success' ? rnd(150, 320) + ' ms' : '—'
    };
    Object.entries(times).forEach(([id, val]) => { const el = document.getElementById(id); if (el) el.textContent = val; });
  }

  document.querySelectorAll('.payload-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.payload-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const target = btn.getAttribute('data-tab');
      document.querySelectorAll('.payload-tab-content').forEach(c => {
        c.classList.remove('active');
        c.style.display = 'none';
      });
      const content = document.getElementById('tab-' + target);
      if (content) { content.classList.add('active'); content.style.display = 'block'; }
    });
  });

  const closeDrawerBtn = document.getElementById('close-drawer');
  if (closeDrawerBtn) closeDrawerBtn.addEventListener('click', () => {
    const drawer = document.getElementById('detail-drawer');
    if (drawer) drawer.classList.remove('open');
  });

  /* ================================================================
     9. SIMULATION ENGINE (live updates)
     ================================================================ */
  function runSimulationTick() {
    if (!isAgentActive || backendMode) return;
    const now = new Date();
    const newReq = generateRequest(now);
    requestPool.unshift(newReq);
    if (requestPool.length > 200) requestPool.pop();

    recalcAggregateStats();

    const hr = now.getHours();
    stats.hourlyRequests[hr] = (stats.hourlyRequests[hr] || 0) + 1;
    const day = now.getDay() === 0 ? 6 : now.getDay() - 1;
    stats.weeklyRequests[day] = (stats.weeklyRequests[day] || 0) + 1;

    stats.waitingQueue = Math.max(1, stats.waitingQueue + rnd(-1, 1));
    stats.processingQueue = Math.max(1, stats.processingQueue + rnd(-1, 1));

    if (newReq.status === 'Escalated' && newReq.confidence < 70) stats.lowConfidencePredictions++;
    if (newReq.reasons.some(r => r.includes('not found in the current zone whitelist'))) stats.unauthorizedRequests++;

    updateHealthKPIs();
    updateQueueBoard();
    updateQualityMetrics();
    updateDashboardKPIs();
    updateParamMetrics();
    refreshCharts();
    renderTimeline();
    renderAuditTable();
    renderAuditPageTable();
    renderEscalationQueue();
    logTerminal([
      { text: `[${newReq.time}] Email received from ${newReq.sender} (${newReq.zone})`, cls: 'text-muted' },
      { text: `[${newReq.time}] Intent classified: ${newReq.intent} (confidence ${newReq.confidence}%)` },
      { text: `[${newReq.time}] ${newReq.status === 'Success' ? '✔ Success response received (' + newReq.duration + ')' : newReq.status === 'Escalated' ? '⚠ Escalated to human supervisor' : newReq.status === 'Rejected' ? '✖ Invalid intent — rejected' : '⏳ Processing...'}`,
        cls: newReq.status === 'Success' ? 'text-success' : newReq.status === 'Escalated' ? 'text-warning' : newReq.status === 'Rejected' ? 'text-danger' : 'text-muted' }
    ]);

    // occasionally surface a fresh alert
    if (Math.random() < 0.12) {
      const templates = [
        { severity: 'warning', message: `Low-confidence classification requiring review (${newReq.confidence}%) — ${newReq.zone}`, region: newReq.zone },
        { severity: 'critical', message: `SNOC API timeout on ${newReq.apiRequest ? newReq.apiRequest.endpoint : '/v1/pos/unlock'}`, region: newReq.zone },
        { severity: 'warning', message: `High email traffic detected in ${newReq.zone}`, region: newReq.zone }
      ];
      const t = pick(templates);
      activeAlerts.unshift({ id: 'A' + Date.now(), severity: t.severity, message: t.message, time: fmtTime(now), region: t.region, status: 'Active' });
      if (activeAlerts.length > 12) activeAlerts.pop();
      renderAlerts();
    }
  }

  /* ================================================================
     10. UI EVENT HANDLERS
     ================================================================ */
  document.getElementById('login-form').addEventListener('submit', e => {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim(), password = document.getElementById('login-password').value;
    const user = getUsers().find(u => u.username === username && u.password === password);
    document.getElementById('login-error').textContent = user ? '' : 'Invalid username or password.';
    if (user) { localStorage.setItem(SESSION_KEY, JSON.stringify(user)); applySession(user); }
  });
  document.getElementById('treatment-form').addEventListener('submit', e => {
    if (e.submitter && e.submitter.value === 'confirm' && pendingTreatment) resolveEscalatedRequest(pendingTreatment.id, pendingTreatment.decision, document.getElementById('treatment-note').value);
    pendingTreatment = null;
  });
  document.getElementById('add-user-form').addEventListener('submit', e => {
    e.preventDefault(); const users = getUsers(), username = document.getElementById('new-user-username').value.trim();
    if (users.some(u => u.username.toLowerCase() === username.toLowerCase())) return alert('That username already exists.');
    users.push({ name: document.getElementById('new-user-name').value.trim(), username, role: document.getElementById('new-user-role').value, password: document.getElementById('new-user-password').value }); saveUsers(users); e.target.reset(); renderUsers();
  });
  document.getElementById('user-profile').addEventListener('click', () => { if (confirm('Sign out of SNOC dashboard?')) { localStorage.removeItem(SESSION_KEY); currentUser = null; document.getElementById('app-container').hidden = true; document.getElementById('login-overlay').hidden = false; } });
  function switchPage(pageKey) {
    document.querySelectorAll('.dashboard-section').forEach(sec => {
      sec.classList.toggle('active-section', sec.getAttribute('data-page') === pageKey);
    });
    document.querySelectorAll('.sidebar-nav li').forEach(li => {
      const link = li.querySelector('a[data-nav]');
      li.classList.toggle('active', !!link && link.getAttribute('data-nav') === pageKey);
    });
    const mainContent = document.querySelector('.dashboard-content');
    if (mainContent) mainContent.scrollTop = 0;
  }
  window.switchPage = switchPage;

  document.querySelectorAll('.sidebar-nav a[data-nav]').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      switchPage(link.getAttribute('data-nav'));
    });
  });

  switchPage('overview');

  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebarEl = document.getElementById('sidebar');
  if (sidebarToggle && sidebarEl) {
    sidebarToggle.addEventListener('click', () => sidebarEl.classList.toggle('collapsed'));
  }

  const agentToggleBtn = document.getElementById('agent-toggle-btn');
  if (agentToggleBtn) {
    agentToggleBtn.addEventListener('click', async () => {
      if (backendMode) {
        try {
          const response = await fetch('/api/agent-toggle', { method: 'POST' });
          if (response.ok) {
            const data = await response.json();
            isAgentActive = data.agent_active;
            updateAgentUI();
            logTerminal([{ text: `[${fmtTime(new Date())}] ${isAgentActive ? 'Agent resumed by TechSupport Ops (Backend)' : 'Agent paused by TechSupport Ops (Backend)'}`, cls: 'text-warning' }]);
          }
        } catch (error) {
          console.error('Failed to toggle agent on backend:', error);
        }
      } else {
        isAgentActive = !isAgentActive;
        updateAgentUI();
        logTerminal([{ text: `[${fmtTime(new Date())}] ${isAgentActive ? 'Agent resumed by TechSupport Ops' : 'Agent paused by TechSupport Ops'}`, cls: 'text-warning' }]);
      }
    });
  }

  const refreshDashboardBtn = document.getElementById('refresh-dashboard-btn');
  if (refreshDashboardBtn) {
    refreshDashboardBtn.addEventListener('click', async () => {
      refreshDashboardBtn.disabled = true;
      const loaded = await loadDashboardData();
      if (loaded) {
        renderTimeline(); renderAuditTable(); renderAuditPageTable(); renderEscalationQueue(); renderAlerts(); refreshCharts();
        updateHealthKPIs(); updateQueueBoard(); updateQualityMetrics();
        updateDashboardKPIs(); updateParamMetrics(); renderWhitelist();
      }
      refreshDashboardBtn.disabled = false;
    });
  }

  const processInboxBtn = document.getElementById('process-inbox-btn');
  if (processInboxBtn) {
    processInboxBtn.addEventListener('click', async () => {
      processInboxBtn.disabled = true;
      processInboxBtn.textContent = 'Processing…';
      try {
        const response = await fetch('/api/simulate-inbox', { method: 'POST' });
        if (!response.ok) throw new Error('Inbox processing failed');
        const result = await response.json();
        await loadDashboardData();
        renderTimeline(); renderAuditTable(); renderAuditPageTable(); renderEscalationQueue(); renderAlerts(); refreshCharts();
        updateHealthKPIs(); updateQueueBoard(); updateQualityMetrics();
        updateDashboardKPIs(); updateParamMetrics(); renderWhitelist();
        logTerminal([{ text: `[${fmtTime(new Date())}] Inbox processed: ${result.processed} new message(s)`, cls: 'text-success' }]);
      } catch (error) {
        logTerminal([{ text: `[${fmtTime(new Date())}] Inbox processing failed`, cls: 'text-danger' }]);
      } finally {
        processInboxBtn.disabled = false;
        processInboxBtn.textContent = 'Process Inbox';
      }
    });
  }

  const globalSearch = document.getElementById('global-search');
  if (globalSearch) globalSearch.addEventListener('input', (e) => {
    renderAuditTable(undefined, e.target.value);
    renderAuditPageTable(undefined, e.target.value);
  });

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      if (globalSearch) globalSearch.focus();
    }
  });

  function wireFilterGroup(scopeSelector, renderFn) {
    document.querySelectorAll(scopeSelector + ' .filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll(scopeSelector + ' .filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderFn(btn.getAttribute('data-filter'), globalSearch ? globalSearch.value : '');
      });
    });
  }
  wireFilterGroup('#quick-filters-row', renderAuditTable);
  wireFilterGroup('#audit-page-filters', renderAuditPageTable);

  const whitelistForm = document.getElementById('whitelist-form');
  if (whitelistForm) {
    whitelistForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const emailInput = document.getElementById('whitelist-email');
      const regionSelect = document.getElementById('whitelist-region');
      const email = emailInput.value.trim();
      if (!email) return;
      supervisors.push({ email, zone: regionSelect.value });
      renderWhitelist();
      logTerminal([{ text: `[${fmtTime(new Date())}] ${email} added to whitelist (${regionSelect.value})`, cls: 'text-success' }]);
      emailInput.value = '';
    });
  }

  document.querySelectorAll('.param-subtab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const scope = btn.closest('.subtab-scope') || document;
      scope.querySelectorAll('.param-subtab-btn').forEach(b => b.classList.remove('active'));
      scope.querySelectorAll('.param-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const panel = scope.querySelector('#param-panel-' + btn.getAttribute('data-param-tab'));
      if (panel) panel.classList.add('active');
    });
  });

  document.querySelectorAll('.mini-toggle').forEach(toggle => {
    toggle.addEventListener('click', () => toggle.classList.toggle('on'));
  });

  const notifTrigger = document.getElementById('notifications-trigger');
  const notifDropdown = document.getElementById('notifications-dropdown');
  if (notifTrigger && notifDropdown) {
    notifTrigger.addEventListener('click', (e) => { e.stopPropagation(); notifDropdown.classList.toggle('show'); });
  }
  document.addEventListener('click', (e) => {
    if (notifDropdown && !notifDropdown.contains(e.target) && e.target !== notifTrigger) notifDropdown.classList.remove('show');
  });

  function updateClocks() {
    setInterval(() => {
      const timeStr = fmtTime(new Date());
      ['last-sync-time', 'sys-last-sync'].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = timeStr; });
      const footer = document.getElementById('footer-sync-time');
      if (footer) footer.textContent = fmtDate(new Date());
    }, 1000);
  }

  /* ================================================================
     11. INITIALIZATION
     ================================================================ */
  async function initializeDashboard() {
    try { const session = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); if (session && getUsers().some(u => u.username === session.username)) applySession(session); } catch (_) { localStorage.removeItem(SESSION_KEY); }
    setupLanguageSwitcher();
    seedAlerts();
    recalcAggregateStats();
    initCharts();
    generateHeatmap();
    renderTimeline();
    renderAuditTable('all', '');
    renderAuditPageTable('all', '');
    renderEscalationQueue();
    renderAlerts();
    seedConsole();
    updateHealthKPIs();
    updateQueueBoard();
    updateQualityMetrics();
    updateDashboardKPIs();
    updateParamMetrics();
    renderWhitelist();
    updateClocks();

    const backendLoaded = await loadDashboardData();
    if (!backendLoaded) {
      seedRequestPool();
      recalcAggregateStats();
    }

    renderTimeline();
    renderAuditTable('all', '');
    renderAuditPageTable('all', '');
    renderEscalationQueue();
    renderAlerts();
    refreshCharts();
    seedConsole();
    updateHealthKPIs();
    updateQueueBoard();
    updateQualityMetrics();
    updateDashboardKPIs();
    updateParamMetrics();
    renderWhitelist();

    setTimeout(() => {
      const skeleton = document.getElementById('skeleton-screen');
      if (skeleton) {
        skeleton.classList.add('fade-out');
        setTimeout(() => { skeleton.style.display = 'none'; }, 500);
      }
      if (!backendMode) {
        simulationTimer = setInterval(runSimulationTick, 4000);
      } else {
        window.clearInterval(simulationTimer);
        setInterval(loadDashboardData, 15000);
      }
    }, 900);
  }

  initializeDashboard();

});