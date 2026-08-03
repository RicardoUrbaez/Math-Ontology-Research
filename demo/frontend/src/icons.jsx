export function Icon({ name, className = "" }) {
  const common = {
    className: `icon ${className}`,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true"
  };

  if (name === "sigma") {
    return (
      <svg {...common}>
        <path d="M18 5H7l6 7-6 7h11" />
      </svg>
    );
  }
  if (name === "upload") {
    return (
      <svg {...common}>
        <path d="M12 16V4" />
        <path d="m7 9 5-5 5 5" />
        <path d="M5 20h14" />
      </svg>
    );
  }
  if (name === "eye") {
    return (
      <svg {...common}>
        <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
        <circle cx="12" cy="12" r="2.5" />
      </svg>
    );
  }
  if (name === "external") {
    return (
      <svg {...common}>
        <path d="M14 5h5v5" />
        <path d="m19 5-8 8" />
        <path d="M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
      </svg>
    );
  }
  if (name === "close") {
    return (
      <svg {...common}>
        <path d="m6 6 12 12" />
        <path d="M18 6 6 18" />
      </svg>
    );
  }
  if (name === "chevron-left" || name === "chevron-right") {
    return (
      <svg {...common}>
        <path d={name === "chevron-left" ? "m15 18-6-6 6-6" : "m9 18 6-6-6-6"} />
      </svg>
    );
  }
  if (name === "zoom-in" || name === "zoom-out") {
    return (
      <svg {...common}>
        <circle cx="10.5" cy="10.5" r="5.5" />
        <path d="m15 15 4 4" />
        <path d="M8 10.5h5" />
        {name === "zoom-in" ? <path d="M10.5 8v5" /> : null}
      </svg>
    );
  }
  if (name === "spark") {
    return (
      <svg {...common}>
        <path d="M12 3v4" />
        <path d="M12 17v4" />
        <path d="M3 12h4" />
        <path d="M17 12h4" />
        <path d="m6.5 6.5 2.8 2.8" />
        <path d="m14.7 14.7 2.8 2.8" />
        <path d="m17.5 6.5-2.8 2.8" />
        <path d="m9.3 14.7-2.8 2.8" />
      </svg>
    );
  }
  if (name === "play") {
    return (
      <svg {...common} fill="currentColor" stroke="none">
        <path d="M8 5.5v13l11-6.5-11-6.5Z" />
      </svg>
    );
  }
  if (name === "stop") {
    return (
      <svg {...common} fill="currentColor" stroke="none">
        <rect x="7" y="7" width="10" height="10" rx="1.5" />
      </svg>
    );
  }
  if (name === "pause") {
    return (
      <svg {...common} fill="currentColor" stroke="none">
        <rect x="7" y="5" width="3.5" height="14" rx="1" />
        <rect x="13.5" y="5" width="3.5" height="14" rx="1" />
      </svg>
    );
  }
  if (name === "download") {
    return (
      <svg {...common}>
        <path d="M12 4v11" />
        <path d="m7.5 11 4.5 4.5 4.5-4.5" />
        <path d="M5 20h14" />
      </svg>
    );
  }
  if (name === "wave") {
    return (
      <svg {...common}>
        <path d="M4 13v-2" />
        <path d="M8 17V7" />
        <path d="M12 20V4" />
        <path d="M16 17V7" />
        <path d="M20 13v-2" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="8" />
    </svg>
  );
}
