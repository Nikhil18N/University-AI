import { lazy, Suspense, useEffect, useState } from "react";
import ChatPage from "./pages/ChatPage";
import { setChannel } from "./services/api";
import "./index.css";

const AdminPage = lazy(() => import("./pages/AdminPage"));

/**
 * The admin console is for university staff only. Students never see a link to it.
 * Staff open it by adding #admin to the address (https://<site>/#admin); the console
 * still asks for the admin key. Once opened in a browser tab, the chat header shows
 * an "Admin console" button for that tab only.
 */
function staffMode(): boolean {
  try {
    if (/^#\/?admin\b/i.test(window.location.hash) || new URLSearchParams(window.location.search).has("admin")) {
      sessionStorage.setItem("sru_staff_mode", "1");
      return true;
    }
    return sessionStorage.getItem("sru_staff_mode") === "1";
  } catch {
    return false;
  }
}

/** The embeddable widget (public/widget.js) opens this app with ?mode=widget. */
function isWidgetMode(): boolean {
  try {
    const params = new URLSearchParams(window.location.search);
    return params.get("mode") === "widget" || /^\/widget\/?$/.test(window.location.pathname);
  } catch {
    return false;
  }
}

function App() {
  const widget = isWidgetMode();
  const [isStaff, setIsStaff] = useState<boolean>(staffMode);
  const [view, setView] = useState<"chat" | "admin">(() =>
    /^#\/?admin\b/i.test(window.location.hash) ? "admin" : "chat"
  );

  useEffect(() => {
    const onHash = () => {
      if (/^#\/?admin\b/i.test(window.location.hash)) {
        setIsStaff(staffMode());
        setView("admin");
      }
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const backToChat = () => {
    if (/^#\/?admin\b/i.test(window.location.hash)) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    setView("chat");
  };

  if (widget) {
    setChannel("widget");
    return <ChatPage variant="widget" />;
  }

  return view === "admin" ? (
    <Suspense fallback={null}>
      <AdminPage onBackToChat={backToChat} />
    </Suspense>
  ) : (
    <ChatPage onOpenAdmin={isStaff ? () => setView("admin") : undefined} />
  );
}

export default App;
