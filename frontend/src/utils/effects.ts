/**
 * Interactive audio and visual effects for the University AI Companion.
 */

/**
 * Play a gentle, harmonious chime using the Web Audio API without requiring any audio files.
 */
export function playChime() {
  try {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return;

    const ctx = new AudioContextClass();
    const now = ctx.currentTime;

    // First note (E5 ~ 659Hz)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(659.25, now);
    gain1.gain.setValueAtTime(0.08, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.35);

    // Second note (B5 ~ 987Hz)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.setValueAtTime(987.77, now + 0.1);
    gain2.gain.setValueAtTime(0.08, now + 0.1);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.55);

    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.1);
    osc2.stop(now + 0.55);
  } catch {
    // Audio autoplay restrictions or unsupported
  }
}

/**
 * Trigger celebration confetti particles on the screen.
 */
export function triggerConfetti() {
  const canvas = document.createElement("canvas");
  canvas.style.position = "fixed";
  canvas.style.top = "0";
  canvas.style.left = "0";
  canvas.style.width = "100vw";
  canvas.style.height = "100vh";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "999999";
  document.body.appendChild(canvas);

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    document.body.removeChild(canvas);
    return;
  }

  const dpr = window.devicePixelRatio || 1;
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  ctx.scale(dpr, dpr);

  // Inside the widget on sru.edu.in: the official blues and black only.
  const colors = document.documentElement.dataset.surface === "widget"
    ? ["#194F90", "#297DE5", "#8DBBF0", "#C1E3FC", "#0F0F11", "#123C6E"]
    : ["#10b981", "#0ea5e9", "#f59e0b", "#8b5cf6", "#ec4899", "#3b82f6", "#eab308"];
  const particleCount = 85;
  const particles: Array<{
    x: number;
    y: number;
    w: number;
    h: number;
    color: string;
    vx: number;
    vy: number;
    rotation: number;
    vRot: number;
    opacity: number;
  }> = [];

  for (let i = 0; i < particleCount; i++) {
    particles.push({
      x: window.innerWidth * Math.random(),
      y: window.innerHeight * -0.2 - Math.random() * 120,
      w: 8 + Math.random() * 10,
      h: 5 + Math.random() * 6,
      color: colors[Math.floor(Math.random() * colors.length)],
      vx: (Math.random() - 0.5) * 4.5,
      vy: 3.5 + Math.random() * 5.5,
      rotation: Math.random() * 360,
      vRot: (Math.random() - 0.5) * 12,
      opacity: 1,
    });
  }

  let animationFrameId: number;
  const startTime = Date.now();

  function animate() {
    if (!ctx) return;
    const elapsed = Date.now() - startTime;
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

    let allDone = true;
    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      p.rotation += p.vRot;
      if (elapsed > 2000) {
        p.opacity = Math.max(0, 1 - (elapsed - 2000) / 700);
      }

      if (p.y < window.innerHeight && p.opacity > 0) {
        allDone = false;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rotation * Math.PI) / 180);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.opacity;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      }
    }

    if (allDone || elapsed > 2800) {
      cancelAnimationFrame(animationFrameId);
      if (canvas.parentNode) {
        canvas.parentNode.removeChild(canvas);
      }
    } else {
      animationFrameId = requestAnimationFrame(animate);
    }
  }

  animationFrameId = requestAnimationFrame(animate);
}

/**
 * True only when the server marked this reply as the student's own eligibility result
 * (a fee / scholarship assessment that used their marks or rank). Reply text is not read:
 * phrases like "tuition fee waiver" also appear in hostel, fee-structure and general answers.
 */
export function isEligibleResponse(data: { answer?: string; cards?: any[]; eligible?: boolean }): boolean {
  return data.eligible === true;
}

const CELEBRATED_KEY = "sru-buddy:eligibility-celebrated";
const celebratedInMemory = new Set<string>();

/**
 * Returns true the first time it is called for a chat session, false afterwards, so the
 * eligibility confetti plays once per session, not after every later answer.
 */
export function claimEligibilityCelebration(sessionId: string): boolean {
  const id = sessionId || "default";
  if (celebratedInMemory.has(id)) return false;
  celebratedInMemory.add(id);
  try {
    const seen = JSON.parse(window.localStorage.getItem(CELEBRATED_KEY) || "[]");
    const list: string[] = Array.isArray(seen) ? seen : [];
    if (list.includes(id)) return false;
    window.localStorage.setItem(CELEBRATED_KEY, JSON.stringify([...list.slice(-49), id]));
  } catch {
    // Storage blocked (private mode, previews): the in-memory guard above still limits it to once per page.
  }
  return true;
}

