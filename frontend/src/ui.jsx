import React, { useEffect, useRef, useState } from "react";

function Icon({ name, size = 19, ...props }) {
  const paths = {
    lock: (
      <>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    layers: (
      <>
        <path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 17l10 5 10-5" />
      </>
    ),
    check: (
      <>
        <path d="m9 12 2 2 4-5M12 2l9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4Z" />
      </>
    ),
    activity: (
      <>
        <path d="M3 12h4l3-8 4 16 3-8h4" />
      </>
    ),
    mail: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="m3 7 9 6 9-6" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14m-5-5 5 5-5 5" />
      </>
    ),
    settings: (
      <>
        <path d="M3 6h18M3 18h18M3 12h18" />
        <circle cx="8" cy="6" r="2" />
        <circle cx="16" cy="12" r="2" />
        <circle cx="9" cy="18" r="2" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 7a9 9 0 1 0 1 8M20 3v5h-5" />
      </>
    ),
    close: <path d="m6 6 12 12M6 18 18 6" />,
    play: <path d="m9 5 11 7-11 7V5Z" />,
    document: (
      <>
        <path d="M14 2H5v20h14V7l-5-5Zm0 0v5h5M8 12h8m-8 4h6" />
      </>
    ),
    download: (
      <>
        <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name] || paths.lock}
    </svg>
  );
}

function Badge({ value, children }) {
  const good = [
    "ALLOW",
    "APPROVED",
    "EXECUTED",
    "COMPLETED",
    "ACTIVE",
    "CONSUMED",
    "VERIFIED",
  ];
  const bad = ["DENY", "DENIED", "QUARANTINED", "REVOKED", "FAILED", "EXPIRED"];
  const tone = good.includes(value)
    ? "good"
    : bad.includes(value)
      ? "bad"
      : [
            "REQUIRE_APPROVAL",
            "WAITING_APPROVAL",
            "PENDING",
            "UNVERIFIED",
          ].includes(value)
        ? "warn"
        : "neutral";
  return (
    <span className={"badge " + tone}>
      <span className="badge-dot" />
      {children || String(value || "UNKNOWN").replaceAll("_", " ")}
    </span>
  );
}

function Empty({ icon = "layers", title, children }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name={icon} size={25} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

function Modal({ title, subtitle, close, children, className = "" }) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    const onCancel = (event) => {
      event.preventDefault();
      close();
    };
    dialog.addEventListener("cancel", onCancel);
    return () => {
      dialog.removeEventListener("cancel", onCancel);
      dialog.close();
      previous?.focus();
    };
  }, [close]);
  return (
    <dialog ref={ref} className={"modal " + className}>
      <div className="modal-head">
        <div>
          <span className="eyebrow">CORTEX LOCK / WORKSPACE</span>
          <h2>{title}</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Close dialog"
          onClick={close}
        >
          <Icon name="close" />
        </button>
      </div>
      <p className="muted">{subtitle}</p>
      {children}
    </dialog>
  );
}

function ConnectionDialog({ close, connect, busy, currentKey }) {
  const [key, setKey] = useState(currentKey);
  const [error, setError] = useState("");
  return (
    <Modal
      title="Connect your workspace"
      subtitle="Use the operator key from your local .env file. It stays in this page’s memory and is cleared when the page reloads."
      close={close}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          try {
            await connect(key.trim());
          } catch (err) {
            setError(err.message);
          }
        }}
      >
        <label>
          Operator key
          <input
            type="password"
            name="operator-key"
            autoComplete="off"
            required
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="Paste CORTEX_OPERATOR_KEY"
          />
        </label>
        <div className="connection-note">
          <Icon name="lock" />
          <p>
            Your Gemini API key belongs on the backend. Only the local operator
            key is needed here.
          </p>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button primary full" disabled={busy || !key.trim()}>
          {busy ? "Connecting…" : "Connect workspace"}
          <Icon name="arrow" />
        </button>
      </form>
    </Modal>
  );
}

export { Icon, Badge, Empty, Modal, ConnectionDialog };
