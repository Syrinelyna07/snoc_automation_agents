import { useState, useRef, useCallback, useEffect } from 'react';
import {
  seedRequestPool, seedAlerts, generateRequest,
  initialHourly, initialWeekly, rnd, rndFloat, commas, fmtTime, fmtDate, pick
} from '../data/mockData.js';

const initialStats = {
  emailsProcessed: 4127,
  successOps: 3608,
  escalations: 249,
  rejectedEmails: 176,
  waitingQueue: 4,
  processingQueue: 3,
  failedQueue: 12,
  lowConfidencePredictions: 63,
  missingEntities: 41,
  unauthorizedRequests: 7,
  hourlyRequests: [...initialHourly],
  weeklyRequests: [...initialWeekly]
};

export function useDashboard() {
  const [requestPool, setRequestPool] = useState(() => seedRequestPool(58));
  const [alerts, setAlerts] = useState(() => seedAlerts());
  const [stats, setStats] = useState(initialStats);
  const [isAgentActive, setIsAgentActive] = useState(true);
  const [consoleLines, setConsoleLines] = useState([]);
  const [now, setNow] = useState(new Date());

  const isAgentActiveRef = useRef(isAgentActive);
  useEffect(() => { isAgentActiveRef.current = isAgentActive; }, [isAgentActive]);

  const appendConsole = useCallback((lines) => {
    setConsoleLines(prev => {
      const next = [...prev, ...lines];
      return next.length > 80 ? next.slice(next.length - 80) : next;
    });
  }, []);

  // seed console with the first few requests once, on mount
  useEffect(() => {
    setRequestPool(pool => {
      const recent = pool.slice(0, 8).slice().reverse();
      const seeded = [];
      recent.forEach(req => {
        seeded.push({ text: `[${req.time}] Email received from ${req.sender} (${req.zone})`, cls: 'text-muted' });
        seeded.push({ text: `[${req.time}] Sender verification ${req.status === 'Escalated' && req.reasons.some(r => r.includes('whitelist')) ? 'FAILED — not in whitelist' : 'OK'}` });
        seeded.push({ text: `[${req.time}] Intent classified: ${req.intent} (confidence ${req.confidence}%)` });
        seeded.push({ text: `[${req.time}] Entities extracted: ${req.entity}` });
        if (req.status === 'Success') seeded.push({ text: `[${req.time}] ✔ Success response received (${req.duration})`, cls: 'text-success' });
        else if (req.status === 'Escalated') seeded.push({ text: `[${req.time}] ⚠ Escalated to human supervisor`, cls: 'text-warning' });
        else if (req.status === 'Rejected') seeded.push({ text: `[${req.time}] ✖ Invalid intent — email rejected`, cls: 'text-danger' });
        else seeded.push({ text: `[${req.time}] ⏳ Awaiting SNOC API response...`, cls: 'text-muted' });
      });
      seeded.push({ text: `[${fmtTime(new Date())}] SYSTEM STREAM STABLE — awaiting next batch...`, cls: 'text-muted' });
      setConsoleLines(seeded);
      return pool;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // simulation tick
  useEffect(() => {
    const tick = setInterval(() => {
      if (!isAgentActiveRef.current) return;
      const t = new Date();
      const newReq = generateRequest(t);

      setRequestPool(prev => [newReq, ...prev].slice(0, 200));

      setStats(prev => {
        const hr = t.getHours();
        const day = t.getDay() === 0 ? 6 : t.getDay() - 1;
        const hourlyRequests = [...prev.hourlyRequests];
        hourlyRequests[hr] = (hourlyRequests[hr] || 0) + 1;
        const weeklyRequests = [...prev.weeklyRequests];
        weeklyRequests[day] = (weeklyRequests[day] || 0) + 1;

        return {
          ...prev,
          emailsProcessed: prev.emailsProcessed + 1,
          successOps: prev.successOps + (newReq.status === 'Success' ? 1 : 0),
          escalations: prev.escalations + (newReq.status === 'Escalated' ? 1 : 0),
          rejectedEmails: prev.rejectedEmails + (newReq.status === 'Rejected' ? 1 : 0),
          waitingQueue: Math.max(1, prev.waitingQueue + rnd(-1, 1)),
          processingQueue: Math.max(1, prev.processingQueue + rnd(-1, 1)),
          lowConfidencePredictions: prev.lowConfidencePredictions + (newReq.status === 'Escalated' && newReq.confidence < 70 ? 1 : 0),
          unauthorizedRequests: prev.unauthorizedRequests + (newReq.reasons.some(r => r.includes('not found in the current zone whitelist')) ? 1 : 0),
          hourlyRequests, weeklyRequests
        };
      });

      appendConsole([
        { text: `[${newReq.time}] Email received from ${newReq.sender} (${newReq.zone})`, cls: 'text-muted' },
        { text: `[${newReq.time}] Intent classified: ${newReq.intent} (confidence ${newReq.confidence}%)` },
        {
          text: `[${newReq.time}] ${newReq.status === 'Success' ? '✔ Success response received (' + newReq.duration + ')' : newReq.status === 'Escalated' ? '⚠ Escalated to human supervisor' : newReq.status === 'Rejected' ? '✖ Invalid intent — rejected' : '⏳ Processing...'}`,
          cls: newReq.status === 'Success' ? 'text-success' : newReq.status === 'Escalated' ? 'text-warning' : newReq.status === 'Rejected' ? 'text-danger' : 'text-muted'
        }
      ]);

      if (Math.random() < 0.12) {
        const templates = [
          { severity: 'warning', message: `Low-confidence classification requiring review (${newReq.confidence}%) — ${newReq.zone}`, region: newReq.zone },
          { severity: 'critical', message: `SNOC API timeout on ${newReq.apiRequest ? newReq.apiRequest.endpoint : '/v1/pos/unlock'}`, region: newReq.zone },
          { severity: 'warning', message: `High email traffic detected in ${newReq.zone}`, region: newReq.zone }
        ];
        const chosen = pick(templates);
        setAlerts(prev => [{ id: 'A' + Date.now(), severity: chosen.severity, message: chosen.message, time: fmtTime(t), region: chosen.region, status: 'Active' }, ...prev].slice(0, 12));
      }
    }, 4000);
    return () => clearInterval(tick);
  }, [appendConsole]);

  // clock
  useEffect(() => {
    const clock = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(clock);
  }, []);

  const dismissAlert = useCallback((id) => {
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, status: 'Resolved' } : a));
  }, []);

  const toggleAgent = useCallback(() => {
    setIsAgentActive(prev => {
      const next = !prev;
      appendConsole([{ text: `[${fmtTime(new Date())}] ${next ? 'Agent resumed by TechSupport Ops' : 'Agent paused by TechSupport Ops'}`, cls: 'text-warning' }]);
      return next;
    });
  }, [appendConsole]);

  return {
    requestPool, alerts, stats, isAgentActive, consoleLines, now,
    dismissAlert, toggleAgent,
    fmtTime, fmtDate, commas, rndFloat
  };
}
