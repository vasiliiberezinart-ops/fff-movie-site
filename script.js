document.addEventListener("DOMContentLoaded", () => {
  // ---------- smooth-scroll for in-page anchors ----------
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener("click", e => {
      const id = a.getAttribute("href");
      if (id.length > 1) {
        const t = document.querySelector(id);
        if (t) { e.preventDefault(); t.scrollIntoView({ behavior: "smooth" }); }
      }
    });
  });

  // ---------- cinematic chrome: film edges + frame counter ----------
  if (window.innerWidth > 700) {
    const left = document.createElement("div");
    left.className = "film-edge film-edge-left";
    left.setAttribute("aria-hidden", "true");
    document.body.appendChild(left);
    const right = document.createElement("div");
    right.className = "film-edge film-edge-right";
    right.setAttribute("aria-hidden", "true");
    document.body.appendChild(right);
  }

  const fc = document.createElement("div");
  fc.className = "frame-counter";
  fc.textContent = "FRAME 0001";
  document.body.appendChild(fc);
  const updateFrame = () => {
    const f = String(Math.floor(window.scrollY / 6) + 1).padStart(4, "0");
    fc.textContent = `FRAME ${f}`;
  };
  window.addEventListener("scroll", updateFrame, { passive: true });

  // ---------- clapperboard intro (home only, once per session) ----------
  const leader = document.getElementById("leader");
  if (leader) {
    if (sessionStorage.getItem("seenLeader") === "1") {
      leader.remove();
    } else {
      const flash = document.getElementById("leaderFlash");
      setTimeout(() => flash.classList.add("fire"), 1450);
      setTimeout(() => {
        leader.classList.add("gone");
        setTimeout(() => leader.remove(), 500);
      }, 1750);
      sessionStorage.setItem("seenLeader", "1");
    }
  }

  // ---------- hero-title: split into chars for snake-animation + chromatic ghosts ----------
  const title = document.querySelector(".hero-title");
  if (title) {
    const frag = document.createDocumentFragment();
    let i = 0;
    title.childNodes.forEach(node => {
      if (node.nodeType === Node.TEXT_NODE) {
        for (const ch of node.textContent) {
          const span = document.createElement("span");
          span.className = "ch";
          span.style.setProperty("--i", i++);
          const printable = ch === " " ? " " : ch;
          span.dataset.ch = printable;
          span.textContent = printable;
          frag.appendChild(span);
        }
      } else if (node.nodeName === "BR") {
        frag.appendChild(document.createElement("br"));
      }
    });
    title.innerHTML = "";
    title.appendChild(frag);
    title.dataset.chars = i;
  }

  // ---------- chromatic aberration: cursor (desktop) / scroll (mobile) ----------
  const root = document.documentElement;
  const isCoarse = matchMedia("(pointer: coarse)").matches;
  if (!isCoarse) {
    let pendingMM = false;
    window.addEventListener("mousemove", e => {
      if (pendingMM) return;
      pendingMM = true;
      requestAnimationFrame(() => {
        const ax = (e.clientX / window.innerWidth - 0.5) * 2;
        const ay = (e.clientY / window.innerHeight - 0.5) * 2;
        root.style.setProperty("--ax", ax.toFixed(3));
        root.style.setProperty("--ay", ay.toFixed(3));
        pendingMM = false;
      });
    }, { passive: true });
  } else {
    let pendingScroll = false;
    const updateScrollAberration = () => {
      const sy = window.scrollY;
      const max = (document.body.scrollHeight - window.innerHeight) || 1;
      const ax = Math.sin(sy * 0.004) * 0.9;
      const ay = (sy / max - 0.5) * 1.6;
      root.style.setProperty("--ax", ax.toFixed(3));
      root.style.setProperty("--ay", ay.toFixed(3));
      pendingScroll = false;
    };
    window.addEventListener("scroll", () => {
      if (pendingScroll) return;
      pendingScroll = true;
      requestAnimationFrame(updateScrollAberration);
    }, { passive: true });
    updateScrollAberration();
  }

  // ---------- hero / teaser videos: pause when tab hidden ----------
  const heroVid = document.querySelector(".hero-video");
  if (heroVid) {
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) heroVid.pause();
      else heroVid.play().catch(() => {});
    });
  }

  // ---------- film-card hover: play poster teaser ----------
  document.querySelectorAll(".film-poster").forEach(card => {
    const vid = card.querySelector(".film-poster-video");
    if (!vid) return;
    card.addEventListener("mouseenter", () => {
      vid.currentTime = 0;
      vid.play().catch(() => {});
    });
    card.addEventListener("mouseleave", () => {
      vid.pause();
    });
  });

  // ---------- 3D-tilt for polaroid film cards ----------
  const cards = document.querySelectorAll(".film-card");
  if (cards.length && !isCoarse) {
    cards.forEach(card => {
      const reset = () => {
        card.style.setProperty("--rx", "0deg");
        card.style.setProperty("--ry", "0deg");
      };
      card.addEventListener("mousemove", e => {
        const r = card.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width  - 0.5;
        const py = (e.clientY - r.top)  / r.height - 0.5;
        card.style.setProperty("--rx", (-py * 10).toFixed(2) + "deg");
        card.style.setProperty("--ry", ( px * 10).toFixed(2) + "deg");
      }, { passive: true });
      card.addEventListener("mouseleave", reset);
    });
  }
  // mobile gyro tilt
  if (cards.length && isCoarse && "DeviceOrientationEvent" in window) {
    const startGyro = () => {
      window.addEventListener("deviceorientation", e => {
        const beta = e.beta  || 0;
        const gamma = e.gamma || 0;
        const rx = Math.max(-8, Math.min(8, (beta - 30) * 0.15));
        const ry = Math.max(-8, Math.min(8, gamma * 0.18));
        cards.forEach(c => {
          c.style.setProperty("--rx", rx.toFixed(2) + "deg");
          c.style.setProperty("--ry", ry.toFixed(2) + "deg");
        });
      }, { passive: true });
    };
    if (typeof DeviceOrientationEvent.requestPermission === "function") {
      const ask = () => {
        DeviceOrientationEvent.requestPermission()
          .then(s => { if (s === "granted") startGyro(); })
          .catch(() => {});
      };
      document.addEventListener("touchstart", ask, { once: true, passive: true });
    } else {
      startGyro();
    }
  }

  // ---------- shimmer sweep on cards entering viewport ----------
  if (cards.length && "IntersectionObserver" in window) {
    const sio = new IntersectionObserver(entries => {
      entries.forEach(en => {
        if (en.isIntersecting) {
          en.target.classList.remove("shimmer-fire");
          void en.target.offsetWidth;
          en.target.classList.add("shimmer-fire");
        }
      });
    }, { threshold: 0.4 });
    cards.forEach(c => sio.observe(c));
  }

  // ---------- full-screen teaser slides — play only when visible ----------
  const teaserVideos = document.querySelectorAll("[data-teaser-video]");
  if (teaserVideos.length && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          const v = entry.target;
          if (entry.isIntersecting && entry.intersectionRatio > 0.5) {
            v.currentTime = 0;
            v.play().catch(() => {});
          } else {
            v.pause();
          }
        });
      },
      { threshold: [0, 0.5, 1] }
    );
    teaserVideos.forEach(v => io.observe(v));
  }

  // ---------- cube-flip JS fallback (browsers without animation-timeline: view()) ----------
  const supportsViewTimeline = typeof CSS !== "undefined" && CSS.supports && CSS.supports("animation-timeline: view()");
  if (!supportsViewTimeline) {
    const flippers = document.querySelectorAll(".hero, .films, .teaser, .about, .help, .not-found, .success, .detail");
    if (flippers.length) {
      const isMobile = window.innerWidth < 700;
      const ROT = isMobile ? 38 : 58;
      const TZ  = isMobile ? 160 : 280;
      const PER = isMobile ? 1100 : 1400;
      const updateFlip = () => {
        const vh = window.innerHeight;
        flippers.forEach(s => {
          const r = s.getBoundingClientRect();
          const center = r.top + r.height / 2;
          let p = 1 - center / vh;
          p = Math.max(0, Math.min(1, p));
          const tilt = (0.5 - p) * 2 * ROT;
          const z = -Math.abs(p - 0.5) * 2 * TZ;
          const op = 1 - Math.abs(p - 0.5) * 1.3;
          const blur = Math.abs(p - 0.5) * 4;
          s.style.transform = `perspective(${PER}px) rotateX(${tilt.toFixed(1)}deg) translateZ(${z.toFixed(0)}px)`;
          s.style.opacity = Math.max(0.3, op).toFixed(2);
          s.style.filter = `blur(${blur.toFixed(1)}px)`;
        });
      };
      let pendingFlip = false;
      const onScrollFlip = () => {
        if (pendingFlip) return;
        pendingFlip = true;
        requestAnimationFrame(() => { updateFlip(); pendingFlip = false; });
      };
      window.addEventListener("scroll", onScrollFlip, { passive: true });
      window.addEventListener("resize", onScrollFlip, { passive: true });
      updateFlip();
    }
  }
});
