document.addEventListener("DOMContentLoaded", () => {
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
      // clapper hits at 1.45s → flash → fade out
      setTimeout(() => flash.classList.add("fire"), 1450);
      setTimeout(() => {
        leader.classList.add("gone");
        setTimeout(() => leader.remove(), 500);
      }, 1750);
      sessionStorage.setItem("seenLeader", "1");
    }
  }

  // hero-title snake animation: split into chars, stagger in/out
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
          span.textContent = ch === " " ? " " : ch;
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

  const heroVid = document.querySelector(".hero-video");
  if (heroVid) {
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) heroVid.pause();
      else heroVid.play().catch(() => {});
    });
  }

  // Play teaser videos on hover, pause on leave
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

  // Full-screen teaser slides — play only when visible
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
});
